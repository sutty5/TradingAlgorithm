
import os
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

api_key = os.getenv("ALPACA_API_KEY")
secret = os.getenv("ALPACA_SECRET_KEY")
client = StockHistoricalDataClient(api_key, secret)

def analyze():
    print("Fetching QQQ Data for Analysis...")
    # Time: 14:56 UTC was the trigger. Let's look at 14:30 to 16:00
    req = StockBarsRequest(
        symbol_or_symbols=["QQQ"],
        timeframe=TimeFrame.Minute,
        start=datetime(2025, 12, 23, 14, 30),
        end=datetime(2025, 12, 23, 16, 00)
    )
    bars = client.get_stock_bars(req)
    df = bars.df
    
    # Handle MultiIndex (symbol, timestamp) -> DatetimeIndex
    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index(level=0, drop=True)
    
    # Resample to 2m
    # Alpaca index is timestamp.
    # 2m Resampling:
    df_2m = df.resample('2min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    
    print("\n--- 2m Candle Log (QQQ) ---")
    # We are looking for a SETUP around 14:56
    # Setup: Short Sweep followed by BOS.
    # NQ Short Alpha logic: 
    # 1. PPI (Divergence) - we can't check ES here easily without fetching SPY too, but let's assume valid PPI.
    # 2. Sweep: High > PPI High.
    # 3. BOS: Close < PPI Low.
    
    # Let's print the raw candles to spot the volatility
    print(df_2m.loc['2025-12-23 14:40:00': '2025-12-23 15:10:00'])

    # Let's manually identify the likely candle
    # 14:56 BOS -> This means the candle closing at 14:56 (starts 14:54) or closing 14:58?
    # Log said "14:56:00". Alpaca stream sends bar AFTER close.
    # So the candle that triggered it likely closed at 14:56:00.
    # That would be the 14:54-14:56 candle.
    
    target_candle_time = pd.Timestamp("2025-12-23 14:54:00+00:00")
    
    if target_candle_time in df_2m.index:
        c = df_2m.loc[target_candle_time]
        print(f"\nTrigger Candle (Starts 14:54): Open {c.open}, High {c.high}, Low {c.low}, Close {c.close}")
        
        # If this was a BOS, the previous High must have been the Sweep Extreme?
        # Or same candle?
        # Sweep Extreme is the Stop.
        # Impulse Low is the Low of THIS candle.
        
        # Scenario A: Sweep and BOS on same candle (Big red candle)
        # Stop = High of *this* candle (Sweep Extreme)
        # Entry = Low + (Range * 0.618)
        # Target = Low (0.0) -> Wait, 1:1 Target?
        # Standard logic: Entry 0.618. Stop 1.0 (High). Target 0.0 (Low).
        # This is a roughly 0.382 distance profit.
        # Wait, Risk = Entry - Stop. Reward = Entry - Target.
        # Risk = (0.618 - 1.0) = 0.382 range.
        # Reward = (0.618 - 0.0) = 0.618 range.
        # R:R = 1.6R. 
        
        # Let's calc values
        high = c.high
        low = c.low
        rng = high - low
        entry = low + (rng * 0.618)
        stop = high
        target = low
        
        print(f"\n--- HYPOTHETICAL SETUP (Same Candle Sweep) ---")
        print(f"Range: {rng:.2f}")
        print(f"Stop (High): {stop:.2f}")
        print(f"Entry (0.618): {entry:.2f}")
        print(f"Target (Low): {target:.2f}")
        print(f"Risk Per Share: ${stop - entry:.2f}")
        
        # Check Outcome in subsequent candles
        print("\n--- PRICE ACTION FOLLOW THROUGH ---")
        future_bars = df.loc['2025-12-23 14:56:00':] # 1m bars
        
        triggered = False
        won = False
        lost = False
        
        for ts, bar in future_bars.iterrows():
            print(f"{ts.strftime('%H:%M')}: H {bar.high} L {bar.low}")
            
            if not triggered:
                if bar.high >= entry:
                    triggered = True
                    print("✅ ENTRY TRIGGERED")
            
            if triggered:
                if bar.low <= target:
                    print("🏆 TARGET HIT (WIN)")
                    won = True
                    break
                if bar.high >= stop:
                    print("❌ STOP HIT (OSS)")
                    lost = True
                    break
                    
        return {
            "pnl": 400 if won else -400 if lost else 0
        }

if __name__ == "__main__":
    analyze()
