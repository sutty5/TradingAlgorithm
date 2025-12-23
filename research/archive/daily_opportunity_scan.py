
import os
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Config
SYMBOLS = ["QQQ", "SPY"]
START_DATE = datetime(2025, 12, 23, 10, 0, tzinfo=timezone.utc) # Start of logical day? or 00:00? Market Open is 14:30 UTC. Pre-market counts? 
# Strategy usually runs 24/7 or RTH? Backtests covered all hours except 8-9 and 18-19.
# Let's start from 00:00 UTC today.
START_DATE = datetime(2025, 12, 23, 0, 0, tzinfo=timezone.utc)
END_DATE = datetime.now(timezone.utc)

MIN_WICK_NQ_L = 0.5
MIN_WICK_ES_S = 0.25

def get_data():
    api_key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    client = StockHistoricalDataClient(api_key, secret)
    
    print(f"Fetching data from {START_DATE} to {END_DATE}...")
    req = StockBarsRequest(
        symbol_or_symbols=SYMBOLS,
        timeframe=TimeFrame.Minute,
        start=START_DATE,
        end=END_DATE,
        feed="iex"
    )
    bars = client.get_stock_bars(req)
    df = bars.df
    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index(level=0)
    return df

def resample(df, tf_str):
    # expect df with index=timestamp
    logic = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum', 'symbol': 'first'}
    df_res = df.resample(tf_str).agg(logic)
    df_res = df_res.dropna()
    return df_res

def get_direction(c):
    if c.close > c.open: return 1
    if c.close < c.open: return -1
    return 0

def check_opportunities(df_qqq, df_spy):
    # We need to iterate by timestamp intersection
    # Common Index
    common_idx = df_qqq.index.intersection(df_spy.index)
    
    signals = []
    
    # PPI State
    ppi_nq_s = None
    ppi_nq_l = None
    ppi_es_s = None
    
    # 2m Loop (NQ Short, ES Short)
    # We need separate processing for 2m and 5m.
    # This function expects pre-resampled DFs for a SINGLE timeframe context OR we do complex loop.
    # Let's do strategies separately.
    pass

def scan_strategy(name, df_target, df_ref, tf_min, direction, min_wick=0.0):
    print(f"\nScanning {name} ({tf_min}m)...")
    # Align
    common = df_target.index.intersection(df_ref.index)
    df_t = df_target.loc[common]
    df_r = df_ref.loc[common]
    
    ppi_age = 0
    ppi_data = {}
    state = "SCANNING"
    count = 0
    
    blocked_hours = [8, 9, 18, 19]
    
    for ts in common:
        t = df_t.loc[ts]
        r = df_r.loc[ts]
        
        if ts.hour in blocked_hours:
            state = "SCANNING"
            continue
            
        t_dir = get_direction(t)
        r_dir = get_direction(r)
        
        if state == "SCANNING":
            if t_dir != 0 and r_dir != 0 and t_dir != r_dir:
                # PPI
                ppi_data = {'high': t.high, 'low': t.low, 'ts': ts}
                ppi_age = 0
                state = "PPI"
                
        elif state == "PPI":
            ppi_age += 1
            if ppi_age > 12:
                state = "SCANNING"
                continue
                
            # Check Sweep
            if direction == "SHORT":
                if t.high > ppi_data['high'] and t.close <= ppi_data['high']:
                    # Wick Check
                    rng = t.high - t.low
                    wick = (t.high - max(t.open, t.close)) / rng if rng > 0 else 0
                    if wick >= min_wick:
                        # Valid Sweep
                        ppi_data['sweep_extreme'] = t.high
                        state = "SWEEP"
            elif direction == "LONG":
                if t.low < ppi_data['low'] and t.close >= ppi_data['low']:
                    rng = t.high - t.low
                    wick = (min(t.open, t.close) - t.low) / rng if rng > 0 else 0
                    if wick >= min_wick:
                        ppi_data['sweep_extreme'] = t.low
                        state = "SWEEP"

        elif state == "SWEEP":
            # BOS Check (Immediate loop continues?)
            # Or does BOS allow aging?
            # Script implies broad aging.
            # Let's check BOS on SAME candle as Sweep? 
            # Logic: If Sweep happened, we are in SWEEP state.
            # Wait, if Sweep happened on THIS candle, can we BOS on THIS candle?
            # Yes, technically.
            # But simple loop usually checks next candle.
            # Let's check BOS now.
            
            is_bos = False
            if direction == "SHORT":
                if t.close < ppi_data['low']:
                    is_bos = True
            else:
                if t.close > ppi_data['high']:
                    is_bos = True
                    
            if is_bos:
                print(f"  [{ts.strftime('%H:%M')}] ⚡ SIGNAL FOUND! (After {ppi_age} bars)")
                count += 1
                state = "FILLED" # Reset
                
    return count

def main():
    df_raw = get_data()
    
    # Split
    df_qqq = df_raw[df_raw['symbol'] == "QQQ"].copy()
    df_spy = df_raw[df_raw['symbol'] == "SPY"].copy()
    
    # Resample 2m
    qqq_2m = resample(df_qqq, "2min")
    spy_2m = resample(df_spy, "2min")
    
    # Resample 5m
    qqq_5m = resample(df_qqq, "5min")
    spy_5m = resample(df_spy, "5min")
    
    total = 0
    total += scan_strategy("NQ Short (2m)", qqq_2m, spy_2m, 2, "SHORT", min_wick=0.0)
    total += scan_strategy("ES Short (2m)", spy_2m, qqq_2m, 2, "SHORT", min_wick=MIN_WICK_ES_S) # SPY is Target!
    total += scan_strategy("NQ Long (5m)", qqq_5m, spy_5m, 5, "LONG", min_wick=MIN_WICK_NQ_L)
    
    print(f"\n✅ Total Opportunities Today: {total}")

if __name__ == "__main__":
    main()
