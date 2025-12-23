
import pandas as pd
import numpy as np
from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState
from data_loader import load_and_prepare_data

def run_forensics():
    # Load Data (Full Set)
    print("Loading Data...")
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    
    # We need to check the "Best" legs. 
    # 1. ES Short 2m
    # 2. NQ Long 5m
    # Let's start with these two as they are the primary drivers.
    
    configs = [
        {
            "name": "ES_SHORT_2m",
            "tf": 2,
            "cfg": BacktestConfig(
                timeframe_minutes=2,
                entry_mode="FIB",
                use_trailing_fib=True,
                fib_entry=0.5,
                fib_stop=1.0,
                fib_target=0.0, # Standard
                entry_expiry_candles=15,
                min_wick_ratio=0.25,
                max_atr=6.0,
                use_macro_filter=True
            )
        },
        {
            "name": "NQ_LONG_5m",
            "tf": 5,
            "cfg": BacktestConfig(
                timeframe_minutes=5,
                entry_mode="FIB",
                use_trailing_fib=True,
                fib_entry=0.5,
                fib_stop=1.0, 
                fib_target=0.0,
                entry_expiry_candles=10,
                min_wick_ratio=0.5,
                use_macro_filter=True
            )
        }
    ]
    
    all_trades = []
    
    for c in configs:
        print(f"Running Forensics for {c['name']}...")
        es, nq = load_and_prepare_data(dbn_path, timeframe_minutes=c['tf'])
        
        engine = GoldenProtocolBacktest(c['cfg'])
        results = engine.run(es, nq)
        
        # Extract trade details
        for t in results.trades:
            if t.state not in [TradeState.WIN, TradeState.LOSS]:
                continue
                
            # Filter for specific leg direction
            if "SHORT" in c['name'] and t.sweep_direction.value != "SHORT": continue
            if "LONG" in c['name'] and t.sweep_direction.value != "LONG": continue
            if "ES" in c['name'] and t.asset != "ES": continue
            if "NQ" in c['name'] and t.asset != "NQ": continue

            # Get Context Data from timestamp
            # We need the candle AT PPI TIME? Or Entry Time?
            # Let's use PPI Time for context (when setup formed)
            # and Fill Time for execution context.
            
            # Re-fetch candle data from DF
            try:
                candle = es.loc[t.ppi_time] if t.asset == "ES" else nq.loc[t.ppi_time]
                
                trade_data = {
                    "strategy": c['name'],
                    "asset": t.asset,
                    "direction": t.sweep_direction.value,
                    "outcome": t.outcome,
                    "pnl": t.pnl,
                    "ppi_time": t.ppi_time,
                    "hour": t.ppi_time.hour,
                    "minute": t.ppi_time.minute,
                    "dow": t.ppi_time.dayofweek,
                    # Metrics
                    "atr": candle.get('atr_14', 0),
                    "rvol": candle.get('rvol', 0),
                    "wick_up": candle.get('wick_ratio_up', 0),
                    "wick_down": candle.get('wick_ratio_down', 0),
                    "body_size": abs(candle['close'] - candle['open']),
                    "candles_to_fill": (t.fill_time - t.ppi_time).total_seconds()/60/c['tf'] if t.fill_time else -1
                }
                all_trades.append(trade_data)
            except KeyError:
                continue
                
    df = pd.DataFrame(all_trades)
    df.to_csv("forensic_trades.csv", index=False)
    print("Saved forensic_trades.csv")
    
    # Quick Analysis Output
    analyze_losers(df)

def analyze_losers(df):
    print("\n--- FORENSIC ANALYSIS REPORT ---")
    
    df['is_loss'] = df['outcome'] == "LOSS"
    
    # 1. Time of Day Analysis
    print("\n[Win Rate by Hour]")
    # Group by Hour (EST conversion? Data is usually UTC. Databento dbn might be UTC.)
    # 14:00 UTC is 9:00 EST (Market Open 9:30).
    # 20:00 UTC is 15:00 EST.
    hourly = df.groupby('hour')['is_loss'].agg(['count', 'mean'])
    hourly['win_rate'] = (1 - hourly['mean']) * 100
    print(hourly)
    
    # 2. ATR Impact
    # Binning ATR
    print("\n[Win Rate by ATR Decile]")
    try:
        df['atr_bin'] = pd.qcut(df['atr'], 5)
        atr_stats = df.groupby('atr_bin', observed=False)['is_loss'].agg(['count', 'mean'])
        atr_stats['win_rate'] = (1 - atr_stats['mean']) * 100
        print(atr_stats)
    except:
        print("Not enough data for ATR bins")

if __name__ == "__main__":
    run_forensics()
