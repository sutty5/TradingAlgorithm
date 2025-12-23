
import pandas as pd

def analyze_phase5():
    try:
        df = pd.read_csv("cloud_optimization_phase5.csv")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print("\n--- PHASE 5: THE BREAKTHROUGH? (Aggressive vs Defender) ---")
    
    # Clean config string if needed, but we extracted entry_mode.
    
    # 1. Compare FREQUENCY
    print("\n[Trade Volume]")
    print(df.groupby('entry_mode')['trades'].sum())
    
    # 2. Compare PROFIT
    print("\n[Total PnL]")
    print(df.groupby('entry_mode')['pnl'].sum())
    
    # 3. Aggregated Stats by Asset
    summary = df.groupby(['asset', 'direction', 'entry_mode']).agg({
        'wr': 'mean',
        'pnl': 'mean',
        'trades': 'mean'
    })
    
    print("\n[Detailed Comparison]")
    print(summary)
    
if __name__ == "__main__":
    analyze_phase5()
