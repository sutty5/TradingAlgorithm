
import pandas as pd

def analyze_phase3():
    try:
        df = pd.read_csv("cloud_optimization_final.csv")
    except FileNotFoundError:
        print("Error: CSV not found.")
        return

    print(f"Total Runs: {len(df)}")
    
    # Clean up column names if needed (script used keys in config dict)
    # The CSV should have columns: config (string representation), asset, direction, wr, trades, pnl
    # Ideally the script exploded the config?
    # No, the script in run_backtest_chunk appends a dict where "config" is a nested dict.
    # THIS IS BAD for CSV.
    # Let me check verify_mechanics.py or the script...
    # The script:
    # df_chunk = pd.DataFrame(results)
    # results = [{"config": cfg_dict, "asset":..., "wr":...}]
    # So "config" column will be a stringified dict.
    # I need to parse it.
    
    import ast
    
    # Expand config
    config_df = pd.json_normalize(df['config'].apply(ast.literal_eval))
    df = pd.concat([df.drop('config', axis=1), config_df], axis=1)
    
    # Group By Hypothesis Parameters
    # 1. Trailing vs Static
    # 2. Target 0.0 vs 0.1
    # 3. By Asset/Direction
    
    with open("analysis_report_phase3.txt", "w", encoding="utf-8") as f:
        f.write("\n--- PHASE 3 SCIENTIFIC VALIDATION RESULTS ---\n")
        
        group_cols = ['asset', 'direction', 'use_trailing_fib', 'fib_target']
        summary = df.groupby(group_cols).agg({
            'wr': 'mean',
            'pnl': 'mean',
            'trades': 'mean',
            'timeframe_minutes': 'count' # Count of configs
        }).reset_index()
        
        summary = summary.sort_values(['asset', 'direction', 'wr'], ascending=[True, True, False])
        
        f.write(summary.to_string())
        
        f.write("\n\n--- WINNER SELECTION (Top 3 Configs per Leg) ---\n")
        for asset in ['ES', 'NQ']:
            for direction in ['SHORT', 'LONG']:
                subset = df[(df['asset'] == asset) & (df['direction'] == direction)]
                top = subset.sort_values('wr', ascending=False).head(3)
                f.write(f"\n{asset} {direction}:\n")
                cols = ['wr', 'pnl', 'trades', 'use_trailing_fib', 'fib_target', 'timeframe_minutes', 'fib_stop', 'entry_expiry_candles']
                f.write(top[cols].to_string(index=False))
                f.write("\n")
    
    print("Analysis saved to analysis_report_phase3.txt")

if __name__ == "__main__":
    analyze_phase3()
