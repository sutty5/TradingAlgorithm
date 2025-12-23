
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict

from data_loader import load_and_prepare_data
from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection

def calculate_wick_ratio(candle: pd.Series, direction: str) -> float:
    """
    Calculate the ratio of the "sweep wick" to the total candle range.
    For SHORT (Bearish Sweep): Upper Wick / Total Range
    For LONG (Bullish Sweep): Lower Wick / Total Range
    """
    total_range = candle['high'] - candle['low']
    if total_range == 0: return 0.0
    
    if direction == "SHORT":
        # Upper wick: High - Max(Open, Close)
        body_top = max(candle['open'], candle['close'])
        wick_size = candle['high'] - body_top
    else:
        # Lower wick: Min(Open, Close) - Low
        body_bottom = min(candle['open'], candle['close'])
        wick_size = body_bottom - candle['low']
        
    return wick_size / total_range

def calculate_rvol(volume: float, history: pd.Series) -> float:
    """Calculate Relative Volume (vs last 20 bars)."""
    avg_vol = history.mean()
    if avg_vol == 0: return 0.0
    return volume / avg_vol

def run_diagnostic():
    # 1. Load Data
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    es_data, nq_data = load_and_prepare_data(dbn_path, timeframe_minutes=2)
    
    # 2. Run "Loose" Backtest (Capture EVERYTHING)
    # We want to see why ES fails and why NQ Longs fail, so we enable everything.
    config = BacktestConfig(
        timeframe_minutes=2,
        use_trend_filter=False, # Disable filters to see raw behavior
        min_atr=0.0,
        fib_entry=0.618 # Standard entry
    )
    
    print("\nRunning Diagnostic Backtest (Loose Constraints)...")
    engine = GoldenProtocolBacktest(config)
    results = engine.run(es_data, nq_data)
    
    # 3. Analyze Trades
    print(f"\nAnalyzing {len(results.trades)} setups...")
    
    analysis_data = []
    
    for trade in results.trades:
        if trade.state not in [TradeState.WIN, TradeState.LOSS]:
            continue # specific analysis on filled trades only for now
            
        # Get Data Context
        # We need the candle corresponding to the SWEEP
        if not trade.sweep_time: continue
        
        sweep_ts = trade.sweep_time
        
        if trade.asset == "ES":
            data = es_data
        else:
            data = nq_data
            
        if sweep_ts not in data.index:
            continue
            
        candle = data.loc[sweep_ts]
        
        # Calculate Metrics
        
        # 1. Wick Ratio
        wick_ratio = calculate_wick_ratio(candle, trade.sweep_direction.name)
        
        # 2. RVOL (Relative Volume)
        # Get last 20 candles volume
        idx_loc = data.index.get_loc(sweep_ts)
        start_loc = max(0, idx_loc - 20)
        vol_history = data['volume'].iloc[start_loc:idx_loc]
        rvol = calculate_rvol(candle['volume'], vol_history)
        
        # 3. ATR Context
        atr = candle.get('atr_14', 0)
        
        # 4. Result
        is_win = 1 if trade.state == TradeState.WIN else 0
        
        analysis_data.append({
            'asset': trade.asset,
            'direction': trade.sweep_direction.name,
            'outcome': trade.state.name,
            'pnl': trade.pnl,
            'hour': sweep_ts.hour,
            'wick_ratio': round(wick_ratio, 3),
            'rvol': round(rvol, 3),
            'atr': round(atr, 2),
            'entry_price': trade.entry_price
        })
        
    df = pd.DataFrame(analysis_data)
    
    # Save raw data
    df.to_csv('diagnostic_results.csv', index=False)
    print("\nDiagnostic data saved to diagnostic_results.csv")
    
    # --- INSIGHT GENERATION ---
    print("\n" + "="*80)
    print("  EINSTEIN DIAGNOSTIC REPORT")
    print("="*80)
    
    # Segment by Asset/Direction
    segments = df.groupby(['asset', 'direction'])
    
    for name, group in segments:
        asset, direction = name
        total = len(group)
        wins = group[group['outcome'] == 'WIN']
        losses = group[group['outcome'] == 'LOSS']
        win_rate = (len(wins) / total * 100) if total > 0 else 0
        
        print(f"\n[{asset} {direction}] Total: {total} | WR: {win_rate:.1f}% | PnL: ${group['pnl'].sum():,.0f}")
        
        if total < 5: continue
        
        # Analyze Wick Ratio
        # Compare Mean Wick Ratio of Wins vs Losses
        mean_wick_win = wins['wick_ratio'].mean() if not wins.empty else 0
        mean_wick_loss = losses['wick_ratio'].mean() if not losses.empty else 0
        print(f"  > Wick Ratio: Wins {mean_wick_win:.2f} vs Losses {mean_wick_loss:.2f}")
        
        # Analyze RVOL
        mean_rvol_win = wins['rvol'].mean() if not wins.empty else 0
        mean_rvol_loss = losses['rvol'].mean() if not losses.empty else 0
        print(f"  > RVOL:       Wins {mean_rvol_win:.2f} vs Losses {mean_rvol_loss:.2f}")

        # Best Hour
        hourly = group.groupby('hour')['outcome'].apply(lambda x: (x == 'WIN').mean())
        best_hours = hourly[hourly > 0.6].index.tolist()
        print(f"  > Best Hours (>60% WR): {best_hours}")


if __name__ == "__main__":
    run_diagnostic()
