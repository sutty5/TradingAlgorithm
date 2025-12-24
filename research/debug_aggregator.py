
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

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

def run_debug():
    print("Running BarAggregator Debug...")
    agg2 = BarAggregator(2)
    agg5 = BarAggregator(5)

    base = datetime(2025, 12, 24, 10, 0, 0)
    
    # Feed 10 minutes of data
    for i in range(10):
        ts = base + timedelta(minutes=i)
        c = Candle(ts, 100+i, 105+i, 95+i, 102+i, 1000, "SPY")
        
        print(f"Feeding {ts.time()}...")
        
        res2 = agg2.add_bar("SPY", c)
        if res2: print(f"  -> TF2 Aggregated: {res2.timestamp.time()} Close={res2.close}")
        
        res5 = agg5.add_bar("SPY", c)
        if res5: print(f"  -> TF5 Aggregated: {res5.timestamp.time()} Close={res5.close}")

if __name__ == "__main__":
    run_debug()
