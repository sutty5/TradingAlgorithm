
import pandas as pd
import numpy as np

def analyze_deep_drill():
    try:
        df = pd.read_csv('deep_drill_results.csv')
    except FileNotFoundError:
        print("Error: deep_drill_results.csv not found.")
        return

    print("\n" + "="*80)
    print("  v6.0 DEEP DRILL ANALYSIS (NQ SHORT)")
    print("="*80)
    
    # Overview
    print(f"\nTotal Configurations Tested: {len(df)}")
    
    # Filters validation
    df = df[df['trades'] >= 20].copy() # Ensure statistical relevance
    print(f"Configurations > 20 trades: {len(df)}")
    
    if df.empty:
        print("No configurations met the minimum trade count.")
        return
        
    # 1. TOP PERFORMERS
    print("\n" + "-"*40)
    print(" TOP 10 BY WIN RATE")
    print("-" * 40)
    cols = ['wr', 'trades', 'pnl', 'fib_entry', 'entry_expiry', 'max_atr', 'min_rvol', 'session_mode', 'use_macro']
    # Check if columns exist
    available_cols = [c for c in cols if c in df.columns]
    
    top_wr = df.sort_values('wr', ascending=False).head(10)
    print(top_wr[available_cols].to_string(index=False))
    
    # 2. PARAMETER SENSITIVITY
    print("\n" + "-"*40)
    print(" PARAMETER INSIGHTS (Avg WR)")
    print("-" * 40)
    
    params = ['session_mode', 'fib_entry', 'entry_expiry', 'max_atr', 'min_rvol', 'use_macro']
    for p in params:
        if p in df.columns:
            print(f"\n--- {p} ---")
            stats = df.groupby(p)['wr'].agg(['mean', 'max', 'count']).sort_values('mean', ascending=False)
            print(stats)

    # 3. GLOBAL BEST
    best = df.sort_values('wr', ascending=False).iloc[0]
    print("\n" + "="*80)
    print(f" BEST CONFIGURATION: {best['wr']:.2f}% WR")
    print("="*80)
    
    with open('best_config_details.txt', 'w') as f:
        for k, v in best.items():
            line = f"{k}: {v}"
            print(line.ljust(20))
            f.write(line + "\n")

    # Check for Grail
    if best['wr'] >= 70.0:
        print("\n🏆 TARGET ACHIEVED: >= 70% WIN RATE FOUND!")
    else:
        print(f"\nTarget not reached. Best WR: {best['wr']:.2f}%")

if __name__ == "__main__":
    analyze_deep_drill()
