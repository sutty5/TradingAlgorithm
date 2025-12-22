
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

# Configuration
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
PAPER_URL = os.getenv("ALPACA_PAPER_ENDPOINT", "https://paper-api.alpaca.markets")

# Validated v5.0 Parameters (QQQ/SPY Proxy)
TIMEFRAME_MINUTES = 2
FIB_ENTRY = 0.618
FIB_STOP = 1.0
FIB_TARGET = 0.0
# NQ Proxy = QQQ
# ES Proxy = SPY
# NQ Proxy = QQQ
# ES Proxy = SPY
SYMBOL_NQ = "QQQ" 
SYMBOL_ES = "SPY"

# Position Management
RISK_PER_TRADE = 400.0 # USD to risk per trade

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("alpaca_trader.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Data Structures (Mirrors backtest_engine.py) ---

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

class BarAggregator:
    """Aggregates 1-minute streaming bars into N-minute candles."""
    def __init__(self, timeframe_minutes: int):
        self.tf = timeframe_minutes
        self.buffer: Dict[str, List[Candle]] = {} # symbol -> list of 1m candles
        
    def add_bar(self, symbol: str, bar) -> Optional[Candle]:
        """
        Add a 1m bar. Checks if it completes a timeframe bucket.
        Alpaca bars come with `timestamp` at the BEGINNING of the minute.
        """
        # Convert Alpaca bar to our Candle
        c = Candle(
            timestamp=bar.timestamp,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            symbol=symbol
        )
        
        if symbol not in self.buffer:
            self.buffer[symbol] = []
            
        self.buffer[symbol].append(c)
        
        # Check complete
        # Logic: If we have 'tf' bars, or if the minute matches logic
        # Simplest: Wait for minute % tf == 0 check is tricky with stream gaps.
        # Robust: Group by truncated timestamp.
        # Live Stream: We receive bars as they close.
        # e.g. 14:00 bar arrives at 14:01:00.
        # 14:01 bar arrives at 14:02:00.
        # We need 14:00 and 14:01 to form the 14:00 2m candle.
        
        # Filter buffer for the current bucket
        # Bucket Start = timestamp - (minute % tf)
        
        current_minute = c.timestamp.minute
        bucket_start_minute = current_minute - (current_minute % self.tf)
        bucket_ts = c.timestamp.replace(minute=bucket_start_minute, second=0, microsecond=0)
        
        # Collect all bars belonging to this bucket
        bucket_bars = [b for b in self.buffer[symbol] 
                       if b.timestamp.replace(minute=b.timestamp.minute - (b.timestamp.minute % self.tf), second=0, microsecond=0) == bucket_ts]
        
        if len(bucket_bars) == self.tf:
            # We have a full candle!
            agg = self._aggregate(bucket_bars, bucket_ts)
            # Clear these from buffer
            self.buffer[symbol] = [b for b in self.buffer[symbol] if b not in bucket_bars]
            return agg
            
        return None
        
    def _aggregate(self, bars: List[Candle], ts: datetime) -> Candle:
        bars.sort(key=lambda x: x.timestamp)
        return Candle(
            timestamp=ts,
            open=bars[0].open,
            high=max(b.high for b in bars),
            low=min(b.low for b in bars),
            close=bars[-1].close,
            volume=sum(b.volume for b in bars),
            symbol=bars[0].symbol
        )

class GoldenProtocolLive:
    """State Machine for Live Trading Logic."""
    def __init__(self):
        self.state = TradeState.SCANNING
        self.setup = {} # Store PPI info
        self.blocked_hours = [8, 9, 18, 19] # UTC
        
    def on_candle_close(self, nq: Candle, es: Candle) -> Optional[Dict]:
        """
        Process aligned 2m candles.
        Returns: Order Signal Dict or None
        """
        logger.info(f"Updated [NQ: {nq.close:.2f} ({nq.direction})] [ES: {es.close:.2f} ({es.direction})]")
        
        # 1. State: SCANNING (Looking for PPI)
        if self.state == TradeState.SCANNING:
            return self._check_ppi(nq, es)
            
        # 2. State: PPI (Looking for Sweep)
        elif self.state == TradeState.PPI:
            return self._check_sweep(nq)
            
        # 3. State: SWEEP (Looking for BOS)
        elif self.state == TradeState.SWEEP:
            return self._check_bos(nq)
            
        return None

    def _check_ppi(self, nq: Candle, es: Candle):
        # Time Filter
        if nq.timestamp.hour in self.blocked_hours:
            return None
        
        # Divergence: Directions must be opposite
        if nq.direction != 0 and es.direction != 0 and nq.direction != es.direction:
            # PPI Found!
            self.setup = {
                'ppi_time': nq.timestamp,
                'ppi_high': nq.high,
                'ppi_low': nq.low,
                'ppi_nq_dir': nq.direction,
                'candles_since': 0
            }
            logger.info(f"💥 PPI DETECTED! NQ Dir: {nq.direction}, ES Dir: {es.direction}")
            self.state = TradeState.PPI
        return None

    def _check_sweep(self, nq: Candle):
        self.setup['candles_since'] += 1
        if self.setup['candles_since'] > 12: # Expiry
            logger.info("PPI Expired (No sweep). Resetting.")
            self.state = TradeState.SCANNING
            return None
            
        # Check Short Sweep (Wick above High, Close Below)
        # NQ MUST BE GREEN OR RED? Strategy says: "Bearish Setup" if PPI was Bearish?
        # Actually strategy lets PRICE dictate.
        # Short Sweep: High > PPI High, Close <= PPI High
        if nq.high > self.setup['ppi_high'] and nq.close <= self.setup['ppi_high']:
            logger.info(f"🧹 BEARISH SWEEP! High {nq.high} > {self.setup['ppi_high']}")
            self.setup['sweep_type'] = 'SHORT'
            self.setup['sweep_extreme'] = nq.high # Fib 1.0
            self.state = TradeState.SWEEP
            return None
            
        # Long Sweep is ignored in v5.0 (Short Only) but logic is here:
        # if nq.low < self.setup['ppi_low'] and nq.close >= self.setup['ppi_low']:
        #    # Long Sweep logic... (Ignored for v5.0)
        
        return None

    def _check_bos(self, nq: Candle):
        # We perform Short Only checks
        if self.setup.get('sweep_type') != 'SHORT':
            self.state = TradeState.SCANNING
            return None
            
        # BOS: Close below PPI Low
        if nq.close < self.setup['ppi_low']:
            logger.info(f"⚡ BOS CONFIRMED! Close {nq.close} < {self.setup['ppi_low']}")
            self.state = TradeState.PENDING # Signal ready
            
            # CALC LEVELS
            fib_1 = self.setup['sweep_extreme'] # Stop
            fib_0 = nq.low # Impulse Low (Target)
            
            fib_range = abs(fib_1 - fib_0)
            entry = fib_0 + (fib_range * FIB_ENTRY)
            stop = fib_1
            target = fib_0 # 0.0 Fib
            
            # --- DYNAMIC POSITION SIZING ---
            # Risk Per Share = |Entry - Stop|
            risk_per_share = abs(entry - stop)
            
            # Safety: Prevent div by zero if range is extremely small (unlikely with filters)
            if risk_per_share < 0.01:
                qty = 1
                logger.warning(f"Risk per share too small (${risk_per_share:.4f}). Defaulting to 1 share.")
            else:
                qty = int(RISK_PER_TRADE / risk_per_share)
            
            # Calculate Total Size for logging
            total_size_usd = qty * entry
            logger.info(f"💎 SIZING: Risk ${RISK_PER_TRADE} | Risk/Share ${risk_per_share:.2f} | Qty {qty} | Total ${total_size_usd:,.2f}")
            
            # Construct Signal
            signal = {
                'symbol': SYMBOL_NQ,
                'side': OrderSide.SELL,
                'qty': qty,
                'entry': round(entry, 2),
                'stop': round(stop, 2),
                'target': round(target, 2)
            }
            logger.info(f"🚀 FIRING SIGNAL: {signal}")
            
            # Reset after firing
            self.state = TradeState.FILLED 
            return signal
            
        return None

class AlpacaPaperTrader:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.client = TradingClient(API_KEY, SECRET_KEY, paper=True)
        self.stream = StockDataStream(API_KEY, SECRET_KEY)
        
        self.aggregator = BarAggregator(TIMEFRAME_MINUTES)
        self.engine = GoldenProtocolLive()
        
        self.latest_nq: Optional[Candle] = None
        self.latest_es: Optional[Candle] = None
        
    async def run(self):
        logger.info(f"Starting Alpaca Trader (Dry Run: {self.dry_run})")
        logger.info(f"Subscribing to {SYMBOL_NQ} and {SYMBOL_ES}...")
        
        # Subscribe
        self.stream.subscribe_bars(self._handle_bar, SYMBOL_NQ, SYMBOL_ES)
        
        # Check Open Orders
        # if not self.dry_run:
        #    self.client.cancel_orders() # Clear state? No, dangerous.
        
        logger.info("Waiting for market data...")
        await self.stream._run_forever()

    async def _handle_bar(self, bar):
        # bar is a Bar object
        symbol = bar.symbol
        candle = self.aggregator.add_bar(symbol, bar)
        
        if candle:
            logger.debug(f"Closed {TIMEFRAME_MINUTES}m Candle: {symbol} {candle.close}")
            if symbol == SYMBOL_NQ:
                self.latest_nq = candle
            elif symbol == SYMBOL_ES:
                self.latest_es = candle
            
            # Sync check: Do we have both for similar timestamp?
            # Basic sync: If timestamps match
            if self.latest_nq and self.latest_es:
                if self.latest_nq.timestamp == self.latest_es.timestamp:
                    signal = self.engine.on_candle_close(self.latest_nq, self.latest_es)
                    if signal:
                        await self._execute_signal(signal)

    async def _execute_signal(self, signal):
        logger.info(f"EXECUTING: {signal}")
        if self.dry_run:
            logger.info("[DRY RUN] Order skipped.")
            return

        # Bracket Order
        # We use Market Order for Entry to ensure fill (simulating Limit-at-touch)
        # Or Limit if strict. Let's use MARKET for Phase 1 Infrastructure Test.
        
        try:
            # Take Profit & Stop Loss details
            # Important: For SHORT, TP < Entry, SL > Entry.
            # Alpaca requires prices.
            
            req = MarketOrderRequest(
                symbol=signal['symbol'],
                qty=signal['qty'],
                side=signal['side'],
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=signal['target']),
                stop_loss=StopLossRequest(stop_price=signal['stop'])
            )
            
            order = self.client.submit_order(req)
            logger.info(f"Order Submitted! ID: {order.id}")
            
        except Exception as e:
            logger.error(f"Order Failed: {e}")

if __name__ == "__main__":
    # Check args
    is_dry = "--dry-run" in sys.argv
    
    trader = AlpacaPaperTrader(dry_run=is_dry)
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(trader.run())
