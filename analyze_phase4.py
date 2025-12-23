
import pandas as pd
import ast

def analyze_phase4():
    try:
        df = pd.read_csv("cloud_optimization_phase4.csv")
    except FileNotFoundError:
        print("Error: CSV not found.")
        return

    # Expand config
    # We notably added 'exclude_hours'
    
    # We need to extract 'exclude_hours' from the stringified dict
    # or just parse the config column
    
    # Let's parse config column
    config_df = pd.json_normalize(df['config'].apply(ast.literal_eval))
    
    # Combine
    df = pd.concat([df.drop('config', axis=1), config_df], axis=1)
    
    # We want to compare performance of the SAME core strategy with and without exclude_hours.
    # Core params: asset, direction, timeframe, fib_entry, fib_stop, etc.
    # Differing param: exclude_hours
    
    # Convert list to string for grouping
    df['filter_name'] = df['exclude_hours'].apply(lambda x: "Filtered" if x else "Original")
    
    print("\n--- PHASE 4: HOURLY FILTER EXPERIMENT RESULTS ---\n")
    
    group_cols = ['asset', 'direction', 'filter_name', 'timeframe_minutes']
    
    summary = df.groupby(group_cols).agg({
        'wr': 'mean',
        'pnl': 'mean',
        'trades': 'mean'
    }).reset_index()
    
    # Pivot for easy comparison
    comparison = summary.pivot(index=['asset', 'direction', 'timeframe_minutes'], columns='filter_name', values=['wr', 'pnl', 'trades'])
    
    # Calculate Diff
    comparison['WR_Delta'] = comparison[('wr', 'Filtered')] - comparison[('wr', 'Original')]
    comparison['PnL_Delta'] = comparison[('pnl', 'Filtered')] - comparison[('pnl', 'Original')]
    comparison['Trade_Reduction'] = comparison[('trades', 'Original')] - comparison[('trades', 'Filtered')]
    
    print(comparison.to_string())
    
    print("\n--- WINNER SELECTION ---")
    # Identify if Filtered is better
    # Better means: Higher WR, similar or higher PnL. 
    # Or significantly higher WR with acceptable PnL drop.
    
    for idx, row in comparison.iterrows():
        asset, direction, tf = idx
        wr_orig = float(row[('wr', 'Original')])
        wr_filt = float(row[('wr', 'Filtered')])
        pnl_orig = float(row[('pnl', 'Original')])
        pnl_filt = float(row[('pnl', 'Filtered')])
        
        if pd.isna(wr_filt) or pd.isna(wr_orig): continue
        
        w_delta = float(row['WR_Delta'])
        p_delta = float(row['PnL_Delta'])
        
        print(f"\n{asset} {direction} {tf}m:")
        print(f"  Original: {wr_orig:.2f}% WR | ${pnl_orig:,.0f}")
        print(f"  Filtered: {wr_filt:.2f}% WR | ${pnl_filt:,.0f}")
        print(f"  Change:   {w_delta:.2f}% WR | ${p_delta:,.0f} PnL")
        
        if wr_filt > wr_orig and pnl_filt > (pnl_orig * 0.9):
            print("  ✅ VERDICT: FILTER WINS (Higher WR, PnL maintained)")
        elif pnl_filt > pnl_orig:
             print("  ✅ VERDICT: FILTER WINS (Higher PnL)")
        else:
            print("  ❌ VERDICT: FILTER FAILS (PnL dropped too much)")

if __name__ == "__main__":
    analyze_phase4()
