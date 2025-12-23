
import pandas as pd
import numpy as np

def run_analysis():
    print("Loading diagnostic results...")
    try:
        df = pd.read_csv('diagnostic_results.csv')
    except FileNotFoundError:
        print("Error: diagnostic_results.csv not found.")
        return

    print("\n" + "="*80)
    print("  EINSTEIN DIAGNOSTIC REPORT (REGENERATED)")
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
        mean_wick_win = wins['wick_ratio'].mean() if not wins.empty else 0
        mean_wick_loss = losses['wick_ratio'].mean() if not losses.empty else 0
        print(f"  > Wick Ratio: Wins {mean_wick_win:.3f} vs Losses {mean_wick_loss:.3f}")
        
        # Analyze RVOL
        mean_rvol_win = wins['rvol'].mean() if not wins.empty else 0
        mean_rvol_loss = losses['rvol'].mean() if not losses.empty else 0
        print(f"  > RVOL:       Wins {mean_rvol_win:.3f} vs Losses {mean_rvol_loss:.3f}")

        # Analyze ATR
        mean_atr_win = wins['atr'].mean() if not wins.empty else 0
        mean_atr_loss = losses['atr'].mean() if not losses.empty else 0
        print(f"  > ATR:        Wins {mean_atr_win:.2f} vs Losses {mean_atr_loss:.2f}")

        # Best Hour
        # Only show hours with > 5 trades
        hourly_counts = group.groupby('hour')['outcome'].count()
        hourly_wins = group[group['outcome'] == 'WIN'].groupby('hour')['outcome'].count()
        
        # Reindex to ensure alignment
        hourly = (hourly_wins / hourly_counts).fillna(0)
        
        # Filter for significant sample size (>10 trades in that hour) and >60% WR
        valid_hours = hourly_counts[hourly_counts >= 10].index
        good_hours = hourly.loc[valid_hours]
        best_hours = good_hours[good_hours > 0.60].index.tolist()
        
        print(f"  > Best Hours (>60% WR, min 10 trades): {best_hours}")

if __name__ == "__main__":
    run_analysis()
