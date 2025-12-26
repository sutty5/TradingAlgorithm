from typing import Dict, List, Optional, Callable
from collections import deque
import datetime

# Types
# Candle: [timestamp_start, open, high, low, close, volume, is_closed]
# We will use a simple class or dict for speed/clarity.

class Candle:
    __slots__ = ['ts', 'open', 'high', 'low', 'close', 'volume', 'closed']
    def __init__(self, ts: int, open_p: float, first_tick_ts: int):
        self.ts = ts # Start time of candle (nano or unix)
        self.open = open_p
        self.high = open_p
        self.low = open_p
        self.close = open_p
        self.volume = 0
        self.closed = False

    def update(self, price: float, size: int):
        if price > self.high: self.high = price
        if price < self.low: self.low = price
        self.close = price
        self.volume += size

class TickEngine:
    def __init__(self):
        self.candles: Dict[str, Candle] = {} # Current performing candle per symbol
        self.history: Dict[str, List[Candle]] = {"ES": [], "NQ": []}
        
        # Callback for strategy when a candle closes
        self.on_candle_close: List[Callable[[str, Candle], None]] = []
        
        # Callback for every tick (for order fills)
        self.on_tick: List[Callable[[int, str, float], None]] = []
        
        # Current time (updated by ticks)
        self.current_time_ns = 0

    def process_tick(self, ts: int, sym: str, price: float, size: int):
        self.current_time_ns = ts
        
        # 1. Update Candle Logic
        if sym not in self.candles:
            # Align ts to nearest 5m floor
            floor_5m = self._align_time(ts)
            self.candles[sym] = Candle(floor_5m, price, ts)
        
        c = self.candles[sym]
        
        # Check if we moved to a new 5m bucket
        # 5 mins in ns = 5 * 60 * 1_000_000_000
        FIVE_MIN_NS = 300_000_000_000
        
        # Strict time check: if ts >= c.ts + FIVE_MIN_NS, close old, open new.
        if ts >= c.ts + FIVE_MIN_NS:
            # CLOSE OLD
            c.closed = True
            self.history[sym].append(c)
            # Notify logic
            for cb in self.on_candle_close:
                cb(sym, c)
            
            # OPEN NEW
            floor_5m = self._align_time(ts)
            # Handle gap: if floor_5m > c.ts + FIVE_MIN_NS, we skipped candles. 
            # For backtesting futures, gaps exist. We just start the new one.
            new_c = Candle(floor_5m, price, ts)
            new_c.volume = size # Initialize with current tick
            self.candles[sym] = new_c
        else:
            # UPDATE CURRENT
            c.update(price, size)
            
        # 2. Tick Event (Entry/Exit Fills)
        for cb in self.on_tick:
            cb(ts, sym, price)

    def _align_time(self, ts: int) -> int:
        # Align to 5 minute floor
        FIVE_MIN_NS = 300_000_000_000
        return (ts // FIVE_MIN_NS) * FIVE_MIN_NS
