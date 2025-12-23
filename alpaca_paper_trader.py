
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
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.common.exceptions import APIError

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# --- CONFIGURATION (v7.0 GOD MODE) ---
# NQ Proxy = QQQ, ES Proxy = SPY
SYMBOL_NQ = "QQQ"
SYMBOL_ES = "SPY"

# Global Risk
RISK_PER_TRADE = 400.0 

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("alpaca_trader_v7.log"),
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
    min_wick: float = 0.0
    max_atr: float = 0.0
    
    # Validation helpers
    def is_short(self): return self.direction == OrderSide.SELL
    def is_long(self): return self.direction == OrderSide.BUY

# --- STRATEGY CONFIGURATIONS (GOD MODE) ---
CONFIGS = [
    # 1. NQ SHORT (The Alpha) - 2m
    StrategyConfig(
        name="NQ_SHORT_2m_ALPHA",
        target_symbol=SYMBOL_NQ,
        ref_symbol=SYMBOL_ES,
        timeframe=2,
        direction=OrderSide.SELL,
        fib_entry=0.618,
        fib_stop=1.0, 
        expiry_candles=5,
        min_wick=0.0
    ),
    # 2. NQ LONG (The Banker) - 5m
    StrategyConfig(
        name="NQ_LONG_5m_BANKER",
        target_symbol=SYMBOL_NQ,
        ref_symbol=SYMBOL_ES,
        timeframe=5,
        direction=OrderSide.BUY,
        fib_entry=0.5,
        fib_stop=1.0,
        expiry_candles=10,
        min_wick=0.5 
    ),
    # 3. ES SHORT (The Validator) - 2m
    StrategyConfig(
        name="ES_SHORT_2m_DEEP",
        target_symbol=SYMBOL_ES,
        ref_symbol=SYMBOL_NQ,
        timeframe=2,
        direction=OrderSide.SELL,
        fib_entry=0.5,
        fib_stop=0.893, # Deep Stop
        expiry_candles=15,
        min_wick=0.25,
        max_atr=6.0 # Not implemented in dry run but recorded
    )
]

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
        self.logger = logging.getLogger(f"STRAT_{config.name}")
        
    def on_candles(self, target_c: Candle, ref_c: Candle) -> Optional[Dict]:
        """Called when matched candles for this TF are ready."""
        
        self.logger.debug(f"Tick: {target_c.close} / {ref_c.close}")

        if self.state == TradeState.SCANNING:
            return self._check_ppi(target_c, ref_c)
        elif self.state == TradeState.PPI:
            return self._check_sweep(target_c)
        elif self.state == TradeState.SWEEP:
            return self._check_bos(target_c)
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
                'age': 0
            }
            self.logger.info(f"💥 PPI Detected on {self.cfg.name}")
            self.state = TradeState.PPI
        return None

    def _check_sweep(self, target: Candle):
        self.ppi_data['age'] += 1
        if self.ppi_data['age'] > 12:
            self.state = TradeState.SCANNING
            return None
            
        # Check Directional Sweep
        # Short Strategy -> Sweep High
        if self.cfg.is_short():
            if target.high > self.ppi_data['high'] and target.close <= self.ppi_data['high']:
                # Wick Check
                rng = target.high - target.low
                wick_size = target.high - max(target.open, target.close)
                wick_ratio = wick_size / rng if rng > 0 else 0
                
                if wick_ratio >= self.cfg.min_wick:
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
                    self.logger.info(f"🧹 Valid Bullish Sweep! Wick: {wick_ratio:.2f}")
                    self.ppi_data['sweep_extreme'] = target.low
                    self.state = TradeState.SWEEP
                    return None
        return None

    def _check_bos(self, target: Candle):
        # Expiry Check (TODO: Implement proper BOS expiry logic if different from total age)
        # Using broad aging for now.
        
        if self.cfg.is_short():
            # BOS = Break below PPI Low
            if target.close < self.ppi_data['low']:
                self.logger.info(f"⚡ BOS Confirmed ({self.cfg.name})")
                return self._create_signal(target)
                
        elif self.cfg.is_long():
            # BOS = Break above PPI High
            if target.close > self.ppi_data['high']:
                self.logger.info(f"⚡ BOS Confirmed ({self.cfg.name})")
                return self._create_signal(target)
                
        return None

    def _create_signal(self, trigger_candle: Candle):
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
            # Target (0.0) -> Impulse Low
            target_px = impulse 
            
        else: # Long
            # 0 is Top (Impulse)? No. Longs impulse is UP.
            # Usually: 0 is Impulse High (Target). 1 is Bottom (Extreme).
            # Retracement goes down from 0 towards 1.
            # Entry 0.5. Stop 0.893 is LOWER/Deeper.
            # Stop Px = Top - (Range * 0.893).
            # Wait, easier math:
            # Bot = Stop Level (Extreme). Top = Impulse.
            # Entry = Top - (Range * 0.5)
            # Stop Px = Top - (Range * StopFib) 
            entry = impulse - (frange * self.cfg.fib_entry)
            stop_px = impulse - (frange * self.cfg.fib_stop)
            target_px = impulse
            
        # Sizing
        risk = abs(entry - stop_px)
        qty = 1
        if risk > 0.01:
            qty = int(RISK_PER_TRADE / risk)
            
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
        
        # Init Strategies
        self.strategies = [StrategyInstance(cfg) for cfg in CONFIGS]
        
    async def run(self):
        logger.info(f"🚀 Starting Alpaca Bot v7.0 GOD MODE (Dry: {self.dry_run})")
        logger.info(f"Loaded {len(self.strategies)} Strategies.")
        
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
            logger.info(f"Processing {tf}m Logic for {candle.timestamp}")
            await self._run_logic(tf, self.pending_candles[tf][SYMBOL_NQ], self.pending_candles[tf][SYMBOL_ES])
            
            # Clear? No, keep until overwritten?
            # Creating a 'processed_timestamps' set is safer, 
            # but simple overwrite works as long as logic is idempotent per bar.
            # Strategy state handles idempotency.
            
    async def _run_logic(self, tf: int, nq: Candle, es: Candle):
        # Run all strategies that match this TF
        for strat in self.strategies:
            if strat.cfg.timeframe == tf:
                # Determine Target/Ref
                target = nq if strat.cfg.target_symbol == SYMBOL_NQ else es
                ref = es if strat.cfg.target_symbol == SYMBOL_NQ else nq
                
                signal = strat.on_candles(target, ref)
                if signal:
                    await self._execute(signal)

    async def _execute(self, signal):
        logger.info(f"⚡ EXECUTION SIGNAL ({signal['strategy']}): {signal}")
        
        if self.dry_run:
            return
            
        req = MarketOrderRequest(
            symbol=signal['symbol'],
            qty=signal['qty'],
            side=signal['side'],
            time_in_force=TimeInForce.DAY,
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
