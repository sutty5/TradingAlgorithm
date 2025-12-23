
import pandas as pd

def analyze():
    try:
        df = pd.read_csv("forensic_trades_cloud.csv")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print(f"Total Trades Analyzed: {len(df)}")
    
    df['is_loss'] = df['outcome'] == "LOSS"
    
    # Hour Analysis
    print("\n--- HOURLY WIN RATES ---")
    hourly = df.groupby('hour')['is_loss'].agg(['count', 'mean'])
    hourly['win_rate'] = (1 - hourly['mean']) * 100
    print(hourly.sort_values('win_rate'))
    
    # ATR Analysis
    print("\n--- ATR DECILE ANALYSIS ---")
    try:
        df['atr_bin'] = pd.qcut(df['atr'], 5)
        atr_stats = df.groupby('atr_bin', observed=False)['is_loss'].agg(['count', 'mean'])
        atr_stats['win_rate'] = (1 - atr_stats['mean']) * 100
        print(atr_stats)
    except:
        print("Not enough data for ATR bins")

    # Day of Week
    # (Optional)

if __name__ == "__main__":
    analyze()
