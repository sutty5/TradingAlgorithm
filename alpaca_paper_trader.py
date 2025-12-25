
import asyncio
import os
import signal
import sys
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
from collections import deque

# Alpaca SDK
from alpaca.data.live import StockDataStream
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.common.exceptions import APIError
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
import pandas as pd
import numpy as np

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# --- CONFIGURATION (v8.1 HONEST GOD MODE - DEC 25) ---
# NQ Proxy = QQQ, ES Proxy = SPY
SYMBOL_NQ = "QQQ"
SYMBOL_ES = "SPY"

# Global Risk
RISK_PER_TRADE_PCT = 2.0  # Risk 2% of account equity per trade
BUYING_POWER_MARGIN = 0.95 # Use 95% of available buying power max

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("alpaca_trader_v8.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# --- DATA STRUCTURES ---

class TradeState(Enum):
    SCANNING = "SCANNING"
    PPI = "PPI"
    SWEEP = "SWEEP"
    PENDING = "PENDING"
    FILLED = "FILLED"

@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str

    @property
    def direction(self) -> int:
        if self.close > self.open: return 1
        if self.close < self.open: return -1
        return 0

@dataclass
class StrategyConfig:
    name: str # e.g. "NQ_SHORT_2m"
    target_symbol: str # QQQ
    ref_symbol: str    # SPY
    timeframe: int     # 2 or 5
    direction: OrderSide # SELL or BUY
    fib_entry: float
    fib_stop: float
    expiry_candles: int
    fib_target: float = 0.0 # Default 0.0 (Impulse End). 0.1 = Extension.
    min_wick: float = 0.0
    max_atr: float = 0.0
    use_macro: bool = True
    
    # Validation helpers
    def is_short(self): return self.direction == OrderSide.SELL
    def is_long(self): return self.direction == OrderSide.BUY

# --- STRATEGY CONFIGURATIONS (GOD MODE) ---
# --- STRATEGY CONFIGURATIONS (V8.1 HONEST GOD MODE - DEC 25) ---
# Entry Expiry: 7 candles (validated via A/B test Dec 25, 2025)
CONFIGS = [
    # 🏆 THE GOLDEN TICKET (ES Short 2m)
    # Win Rate: 75.2% (A/B Tested - 7 candle expiry)
    StrategyConfig(
        name="ES_SHORT_2m_V8.1",
        target_symbol=SYMBOL_ES,  # SPY
        ref_symbol=SYMBOL_NQ,     # QQQ
        timeframe=2,
        direction=OrderSide.SELL,
        fib_entry=0.382,          # Deep Pullback
        fib_stop=1.15,            # Wide Invalidation
        fib_target=0.0,           # Impulse End
        expiry_candles=7,         # V8.1: Changed from 15 to 7
        min_wick=0.25,
        max_atr=6.0
    ),
    # 💰 NQ STANDARD (NQ Long 5m)
    # Win Rate: 70.2% (A/B Tested - 7 candle expiry)
    StrategyConfig(
        name="NQ_LONG_5m_Standard_V8.1",
        target_symbol=SYMBOL_NQ,
        ref_symbol=SYMBOL_ES,
        timeframe=5,
        direction=OrderSide.BUY,
        fib_entry=0.5,
        fib_stop=1.15,
        fib_target=0.0,
        expiry_candles=7,         # V8.1: Changed from 20 to 7
        min_wick=0.5,
        max_atr=0.0,
        use_macro=True
    ),
    # 🚀 NQ EINSTEIN (NQ Long 5m - Aggressive)
    # Win Rate: 78.6% (A/B Tested - 7 candle expiry)
    StrategyConfig(
        name="NQ_LONG_5m_Einstein_V8.1",
        target_symbol=SYMBOL_NQ,
        ref_symbol=SYMBOL_ES,
        timeframe=5,
        direction=OrderSide.BUY,
        fib_entry=0.382,          # Einstein: Shallower entry
        fib_stop=1.15,
        fib_target=0.0,
        expiry_candles=7,
        min_wick=0.0,             # Einstein: No wick filter
        max_atr=0.0,
        use_macro=False           # Einstein: Macro OFF
    )
]

# --- HONEST MACRO TRACKER (DEC 24) ---
class MacroTracker:
    def __init__(self, api_key, secret, symbol="SPY"):
        self.client = StockHistoricalDataClient(api_key, secret)
        self.symbol = symbol
        self.current_trend = 0 # 0=Unknown, 1=Bull, -1=Bear
        self.last_update = None
        self.logger = logging.getLogger("MacroTracker")
        
    def update(self):
        """Fetches recent 1H bars and calculates Shift(1) Trend."""
        try:
            now = datetime.now(timezone.utc)
            # Only update once per hour or on startup
            if self.last_update and (now - self.last_update).total_seconds() < 300:
                return self.current_trend

            self.logger.info("Updating Honest Macro Trend...")
            req = StockBarsRequest(
                symbol_or_symbols=self.symbol,
                timeframe=TimeFrame(1, TimeFrameUnit.Hour),
                limit=200 # Sufficient for EMA50
            )
            bars = self.client.get_stock_bars(req).df
            if bars.empty:
                self.logger.warning("Empty Macro Data")
                return 0
                
            # Logic: Matches data_loader.py
            # 1. Resample to 1H (Alpaca gives 1H bars, but ensure integrity)
            df = bars.reset_index()
            # 2. Calc EMA 50
            df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
            # 3. Macro Trend = Close > EMA
            df['raw_trend'] = np.where(df['close'] > df['ema_50'], 1, -1)
            # 4. SHIFT(1) - The Honest Logic
            # We use the trend of the COMPLETED bar (prev index)
            df['honest_trend'] = df['raw_trend'].shift(1)
            
            # Get latest valid
            last_valid = df.iloc[-1]
            # Verify timestamp? 
            # Alpaca bars are indexed by open time?
            # If current time is 13:15. Last bar is 13:00 (Open).
            # We want the trend derived from the 12:00 Bar (Closed at 13:00).
            # Use 'honest_trend' of the 13:00 bar row?
            # If we shifted raw_trend (calculated on 13:00 close), 
            # shift(1) puts the 12:00 trend onto the 13:00 row.
            # So looking at the LAST row gives us the 12:00 trend.
            # Correct.
            
            trend = int(last_valid['honest_trend']) if not pd.isna(last_valid['honest_trend']) else 0
            self.current_trend = trend
            self.last_update = now
            self.logger.info(f"✅ Honest Macro Trend Updated: {trend} (Shift 1 OK)")
            return trend
            
        except Exception as e:
            self.logger.error(f"Macro Update Failed: {e}")
            return self.current_trend

# --- AGGREGATION ---

class BarAggregator:
    """Aggregates 1m bars into custom timeframe."""
    def __init__(self, timeframe: int):
        self.tf = timeframe
        self.buffer: Dict[str, List[Candle]] = {}
        
    def add_bar(self, symbol: str, bar) -> Optional[Candle]:
        # Convert to Candle
        c = Candle(bar.timestamp, bar.open, bar.high, bar.low, bar.close, bar.volume, symbol)
        
        if symbol not in self.buffer: self.buffer[symbol] = []
        self.buffer[symbol].append(c)
        
        # Determine Bucket
        ts_min = c.timestamp.minute
        bucket_start_min = ts_min - (ts_min % self.tf)
        bucket_ts = c.timestamp.replace(minute=bucket_start_min, second=0, microsecond=0)
        
        # Extract bars for this bucket
        current_bucket_bars = [
            b for b in self.buffer[symbol] 
            if b.timestamp.replace(minute=b.timestamp.minute - (b.timestamp.minute % self.tf), second=0, microsecond=0) == bucket_ts
        ]
        
        if len(current_bucket_bars) == self.tf:
            # Aggregate
            current_bucket_bars.sort(key=lambda x: x.timestamp)
            agg = Candle(
                timestamp=bucket_ts,
                open=current_bucket_bars[0].open,
                high=max(b.high for b in current_bucket_bars),
                low=min(b.low for b in current_bucket_bars),
                close=current_bucket_bars[-1].close,
                volume=sum(b.volume for b in current_bucket_bars),
                symbol=symbol
            )
            # Cleanup
            self.buffer[symbol] = [b for b in self.buffer[symbol] if b not in current_bucket_bars]
            return agg
        return None

# --- STRATEGY EXECUTOR ---

class StrategyInstance:
    """Runs logic for a SINGLE configuration."""
    def __init__(self, config: StrategyConfig):
        self.cfg = config
        self.state = TradeState.SCANNING
        self.ppi_data = {}
        self.age = 0 # Age of PPI in candles
        self.logger = logging.getLogger(f"STRAT_{config.name}")
        
    def _reset(self):
        self.state = TradeState.SCANNING
        self.ppi_data = {}
        self.age = 0
        self.logger.info(f"♻️ Strategy {self.cfg.name} reset to SCANNING.")

    def on_candles(self, target: Candle, ref: Candle, macro_dir: int, equity: float = 100000.0, buying_power: float = 400000.0) -> Optional[Dict]:
        """Called when matched candles for this TF are ready."""
        
        self.logger.debug(f"Tick: {target.close} / {ref.close} | Macro: {macro_dir}")

        # Age check for PPI/Sweep states
        if self.state in [TradeState.PPI, TradeState.SWEEP]:
            self.age += 1
            if self.age > self.cfg.expiry_candles:
                self.logger.info(f"⏰ Strategy {self.cfg.name} Expired ({self.age} candles)")
                self._reset()
                return None

        if self.state == TradeState.SCANNING:
            return self._check_ppi(target, ref)
        elif self.state == TradeState.PPI:
            return self._check_sweep(target, macro_dir)
        elif self.state == TradeState.SWEEP:
            return self._check_bos(target, equity, buying_power)
        # Pending/Filled handled externally or reset? 
        # For simple bot, auto-reset after fill logic passed up.
        return None

    def _check_ppi(self, target: Candle, ref: Candle):
        # Divergence Check
        if target.direction != 0 and ref.direction != 0 and target.direction != ref.direction:
            # Valid PPI
            self.ppi_data = {
                'high': target.high,
                'low': target.low,
            }
            self.age = 0 # Reset age for new PPI
            self.logger.info(f"💥 PPI Detected on {self.cfg.name}")
            self.state = TradeState.PPI
        return None

    def _check_sweep(self, target: Candle, macro_dir: int):
        # Check Directional Sweep
        # Short Strategy -> Sweep High
        if self.cfg.is_short():
            if target.high > self.ppi_data['high'] and target.close <= self.ppi_data['high']:
                # Wick Check
                rng = target.high - target.low
                wick_size = target.high - max(target.open, target.close)
                wick_ratio = wick_size / rng if rng > 0 else 0
                
                if wick_ratio >= self.cfg.min_wick:
                    # MACRO FILTER
                    if self.cfg.use_macro and macro_dir != -1:
                        self.logger.info(f"🛑 Macro Mismatch (Trend {macro_dir}, Need -1). Sweep ignored.")
                        return None
                        
                    self.logger.info(f"🧹 Valid Bearish Sweep! Wick: {wick_ratio:.2f}")
                    self.ppi_data['sweep_extreme'] = target.high
                    self.state = TradeState.SWEEP
                    return None
                    
        # Long Strategy -> Sweep Low
        elif self.cfg.is_long():
            if target.low < self.ppi_data['low'] and target.close >= self.ppi_data['low']:
                # Wick Check
                rng = target.high - target.low
                wick_size = min(target.open, target.close) - target.low
                wick_ratio = wick_size / rng if rng > 0 else 0
                
                if wick_ratio >= self.cfg.min_wick:
                    # MACRO FILTER
                    if self.cfg.use_macro and macro_dir != 1:
                        self.logger.info(f"🛑 Macro Mismatch (Trend {macro_dir}, Need 1). Sweep ignored.")
                        return None

                    self.logger.info(f"🧹 Valid Bullish Sweep! Wick: {wick_ratio:.2f}")
                    self.ppi_data['sweep_extreme'] = target.low
                    self.state = TradeState.SWEEP
                    return None
        return None

    def _check_bos(self, target: Candle, equity: float, buying_power: float):
        # Expiry Check (TODO: Implement proper BOS expiry logic if different from total age)
        # Using broad aging for now.
        
        if self.cfg.is_short():
            # BOS = Break below PPI Low
            if target.close < self.ppi_data['low']:
                self.logger.info(f"⚡ BOS Confirmed ({self.cfg.name})")
                return self._create_signal(target, equity, buying_power)
                
        elif self.cfg.is_long():
            # BOS = Break above PPI High
            if target.close > self.ppi_data['high']:
                self.logger.info(f"⚡ BOS Confirmed ({self.cfg.name})")
                return self._create_signal(target, equity, buying_power)
                
        return None

    def _create_signal(self, trigger_candle: Candle, equity: float, buying_power: float):
        # Calc Levels
        stop_level = self.ppi_data['sweep_extreme']
        impulse = trigger_candle.low if self.cfg.is_short() else trigger_candle.high
        
        # Range
        # Short: Top (Stop) -> Bot (Impulse)
        # Long: Bot (Stop) -> Top (Impulse)
        frange = abs(stop_level - impulse)
        
        if self.cfg.is_short():
            entry = impulse + (frange * self.cfg.fib_entry)
            # Deep Stop Logic? 
            # If Stop is 0.893, it means RISK is smaller.
            # Stop Px = Top - (Range * 0.893)? 
            # No, standard Fib retracement. 1.0 is full retrace to top.
            # If we enter at 0.5 and stop at 0.893 (Deep), Stop is closer to Entry than 1.0
            # Wait. 0 is Bottom (Impulse). 1 is Top (Exteme).
            # Entry 0.5. Stop 0.893 is HIGHER up. 
            # Correct.
            stop_px = impulse + (frange * self.cfg.fib_stop)
            # Target Logic: Impulse (Low) is 0.0. Extension (0.1) is LOWER.
            # Target = Impulse - (Range * fib_target)
            target_px = impulse - (frange * self.cfg.fib_target)
            
        else: # Long
            # 0 is Top (Impulse). 1 is Bottom (Extreme).
            # Entry = Top - (Range * 0.5)
            # Stop Px = Top - (Range * StopFib) 
            # Target Logic: Impulse (High) is 0.0. Extension (0.1) is HIGHER.
            # Target = Impulse + (Range * fib_target)
            
            entry = impulse - (frange * self.cfg.fib_entry)
            stop_px = impulse - (frange * self.cfg.fib_stop)
            target_px = impulse + (frange * self.cfg.fib_target)
            
        # Sizing
        risk_per_share = abs(entry - stop_px)
        qty = 0
        if risk_per_share > 0.01:
            # Dynamic Risk Calculation
            risk_amount = (equity * RISK_PER_TRADE_PCT) / 100.0
            raw_qty = risk_amount / risk_per_share
            
            # Capacity Check (Buying Power)
            notional = raw_qty * entry
            capacity = buying_power * BUYING_POWER_MARGIN
            
            if notional > capacity:
                self.logger.warning(f"⚠️ Buying Power Limit! Required ${notional:,.2f} but capacity is ${capacity:,.2f}. Clamping.")
                qty = int(capacity / entry)
            else:
                qty = int(raw_qty)
                
            actual_risk = qty * risk_per_share
            self.logger.info(f"💎 SIZING: Equity ${equity:,.2f} | Risk Amount ${risk_amount:,.2f} | Qty {qty} | Actual Risk ${actual_risk:,.2f}")
            
        self.state = TradeState.FILLED # Stop firing
        
        return {
            'symbol': self.cfg.target_symbol,
            'side': self.cfg.direction,
            'qty': qty,
            'entry': round(entry, 2),
            'stop': round(stop_px, 2),
            'target': round(target_px, 2),
            'strategy': self.cfg.name
        }


# --- MAIN TRADER ---

class AlpacaPaperTrader:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        
        # Init Clients
        api_key = os.getenv("ALPACA_API_KEY")
        secret = os.getenv("ALPACA_SECRET_KEY")
        self.client = TradingClient(api_key, secret, paper=True)
        self.stream = StockDataStream(api_key, secret)
        
        # Init Aggregators (Unique set of TFs)
        self.tfs = list(set([c.timeframe for c in CONFIGS])) # [2, 5]
        self.aggregators = {tf: BarAggregator(tf) for tf in self.tfs}
        
        # pending_candles[tf][symbol] = Candle
        self.pending_candles = {tf: {} for tf in self.tfs}
        
        # Macro
        self.macro = MacroTracker(api_key, secret, SYMBOL_ES) # Use ES/SPY for macro
        
        # Init Strategies
        self.strategies = [StrategyInstance(cfg) for cfg in CONFIGS]
        
    async def run(self):
        logger.info(f"🚀 Starting Alpaca Bot v8.1 HONEST GOD MODE (Dry: {self.dry_run})")
        logger.info(f"Loaded {len(self.strategies)} Strategies (7-candle expiry).")
        
        self.stream.subscribe_bars(self._handle_bar, SYMBOL_NQ, SYMBOL_ES)
        await self.stream._run_forever()
        
    async def _handle_bar(self, bar):
        # Route 1m bar to ALL aggregators
        for tf, agg in self.aggregators.items():
            candle = agg.add_bar(bar.symbol, bar)
            if candle:
                await self._on_tf_candle(tf, candle)
                
    async def _on_tf_candle(self, tf: int, candle: Candle):
        """Called when a consolidated X-minute candle closes."""
        logger.debug(f"Closed {tf}m Candle: {candle.symbol} {candle.close}")
        
        # Store
        self.pending_candles[tf][candle.symbol] = candle
        
        # Check Synchronization
        # We process logic only when we have BOTH NQ and ES for this TF and timestamp
        other_sym = SYMBOL_ES if candle.symbol == SYMBOL_NQ else SYMBOL_NQ
        other_candle = self.pending_candles[tf].get(other_sym)
        
        if other_candle and other_candle.timestamp == candle.timestamp:
            logger.info(f"🔄 TF {tf}m Synced: {candle.timestamp}")
            
            # Fetch Account Info for Dynamic Sizing
            try:
                account = self.client.get_account()
                equity = float(account.equity)
                buying_power = float(account.buying_power)
            except Exception as e:
                logger.error(f"❌ Failed to fetch account data: {e}")
                equity = 100000.0 # Default fallback for safety
                buying_power = 400000.0
            
            # Update Macro
            macro_dir = self.macro.update()
            
            # Check All Strategies
            for strat in self.strategies:
                if strat.cfg.timeframe == tf:
                    # Determine which is target and which is ref
                    target_candle = self.pending_candles[tf].get(strat.cfg.target_symbol)
                    ref_candle = self.pending_candles[tf].get(strat.cfg.ref_symbol)
                    
                    if target_candle and ref_candle:
                        signal = strat.on_candles(target_candle, ref_candle, macro_dir, equity, buying_power)
                        if signal:
                            await self._execute(signal)

    async def _execute(self, signal):
        logger.info(f"⚡ EXECUTION SIGNAL ({signal['strategy']}): {signal}")
        
        if self.dry_run:
            return
            
        req = LimitOrderRequest(
            symbol=signal['symbol'],
            qty=signal['qty'],
            side=signal['side'],
            time_in_force=TimeInForce.DAY,
            limit_price=signal['entry'],
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=signal['target']),
            stop_loss=StopLossRequest(stop_price=signal['stop'])
        )
        try:
            order = self.client.submit_order(req)
            logger.info(f"✅ Order Submitted: {order.id}")
            # Reset Strategy State?
            # StrategyInstance sets state to FILLED. 
            # We need to reset it to SCANNING eventually?
            # For this bot, let's keep it simple: restart bot or implement 'Reset' logic
            # Implementing Quick Reset for continuous trading:
            for s in self.strategies:
                if s.cfg.name == signal['strategy']:
                    s.state = TradeState.SCANNING
                    logger.info(f"♻️ Strategy {s.cfg.name} reset to SCANNING.")
        except Exception as e:
            logger.error(f"❌ Order Failed: {e}")

if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    t = AlpacaPaperTrader(dry_run=is_dry)
    asyncio.run(t.run())
