
from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
import pandas as pd
from datetime import datetime
import numpy as np

def create_mock_data():
    """Create a controlled scenario to test Trailing vs Static."""
    # Scenario: Bearish Setup
    # 1. PPI (Divergence)
    # 2. Sweep High
    # 3. BOS Low
    # 4. Entry Fill (Retrace)
    # 5. Price goes Lower (Profit) -> Trailing Test
    # 6. Price Reverses -> Stop Test
    
    dates = pd.date_range(start="2025-01-01 09:30", periods=20, freq="2min")
    data = []
    
    # 0: PPI Setup (ES Green, NQ Red)
    # 1: Sweep (Wick High)
    # 2: BOS (Close Low)
    # 3: Pending
    # 4: Fill (Retrace Up)
    # 5: Drop (Profit) -> Fib_0 should move if trailing
    # 6: Drop more
    # 7: Reversal
    
    base_price = 1000.0
    
    # PPI Candle
    data.append([1000, 1010, 990, 1005]) # Green
    
    # Sweep Candle (High 1020, Close 1000)
    data.append([1005, 1020, 995, 1000]) 
    
    # BOS Candle (Close 980 - below PPI Low 990)
    data.append([1000, 1000, 970, 980]) # Low is 970. Initial fib_0 = 970. fib_1 = 1020. Range = 50.
    
    # Pending 1 (No fill yet)
    data.append([980, 990, 975, 985]) 
    
    # Fill Candle (High hits Entry 0.5)
    # Entry = 970 + (0.5 * 50) = 995.
    data.append([985, 1000, 980, 990]) # High 1000 triggers fill.
    
    # Move Lower (New Low 960) -> Should update Trailing Fib if ON
    # If Trailing: fib_0 = 960. Range = 60. Entry stays locked at 995? 
    # NO. Entry formula uses CURRENT fib_0 and fib_1.
    # WAIT. The code says:
    # "Locking: Range locks when entry is filled"
    # Let's check logic:
    # _process_pending_phase loops. It updates fib_0. THEN checks fill.
    # Once filled, it goes to FILLED phase.
    # In FILLED phase, it does NOT update fibs.
    # SO TRAILING ONLY MATTERS BEFORE FILL.
    # Correct. The "Golden Protocol" uses trailing fibs *to define the entry*.
    # Once you are in, you are in.
    
    data.append([990, 990, 960, 970]) 
    
    # ... more data
    for i in range(14):
        data.append([970, 980, 960, 970])
        
    df = pd.DataFrame(data, columns=['open', 'high', 'low', 'close'], index=dates)
    # Add dummy cols for filters
    df['atr_14'] = 10.0
    df['rvol'] = 2.0
    return df

def test_mechanics():
    es = create_mock_data()
    nq = create_mock_data() # Same data, but we force divergence manually in code or just use logic
    
    # Force PPI: ES Green, NQ Red at index 0
    # Current mock data is Green. So ES is fine.
    # Make NQ Red at index 0.
    # Must assign matching columns: open, high, low, close, atr, rvol
    nq.iloc[0] = [1000, 1010, 990, 995, 10.0, 2.0] # Close < Open
    
    print("--- Test A: Trailing ON (Standard v7) ---")
    cfg_a = BacktestConfig(use_trailing_fib=True, fib_target=0.0)
    engine_a = GoldenProtocolBacktest(cfg_a)
    res_a = engine_a.run(es, nq)
    if res_a.trades:
        t = res_a.trades[0]
        print(f"Trade State: {t.state}")
        print(f"Fib_0: {t.fib_0}")
        print(f"Entry: {t.entry_price}")
        print(f"Target: {t.target_price}")
    
    print("\n--- Test B: Trailing OFF (Original) ---")
    cfg_b = BacktestConfig(use_trailing_fib=False, fib_target=0.1)
    engine_b = GoldenProtocolBacktest(cfg_b)
    res_b = engine_b.run(es, nq)
    if res_b.trades:
        t = res_b.trades[0]
        print(f"Trade State: {t.state}")
        print(f"Fib_0: {t.fib_0}")
        print(f"Entry: {t.entry_price}")
        print(f"Target: {t.target_price}")

if __name__ == "__main__":
    test_mechanics()
