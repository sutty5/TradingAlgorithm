import pandas as pd
import ast
import sys

def analyze():
    pd.set_option('display.max_colwidth', None)
    pd.set_option('display.max_columns', None)

    df = pd.read_csv("optimization_honest_results.csv")
    
    # Clean
    if isinstance(df.iloc[0]['config'], str):
        df['config_dict'] = df['config'].apply(ast.literal_eval)
    else:
        df['config_dict'] = df['config']

    viable = df[df['trades'] >= 30].copy()
    
    with open("research/honest_winners.txt", "w", encoding="utf-8") as f:
        f.write(f"Total Tested: {len(df)}\n")
        f.write(f"Viable (>30 trades): {len(viable)}\n\n")
        
        def write_top(df_slice, title):
            f.write(f"{title}\n")
            f.write("="*80 + "\n")
            for i, row in df_slice.iterrows():
                f.write(f"RANK | {row['asset']} {row['direction']} | WR: {row['wr']:.1f}% | Trades: {row['trades']} | PnL: ${row['pnl']:.0f}\n")
                f.write(f"Config: {row['config_dict']}\n")
                f.write("-" * 40 + "\n")
            f.write("\n")

        # 1. Best Win Rate (Viable)
        write_top(viable.sort_values("wr", ascending=False).head(10), "TOP 10 BY WIN RATE (HONEST)")

        # 2. Best PnL (Viable)
        write_top(viable.sort_values("pnl", ascending=False).head(10), "TOP 10 BY PNL (HONEST)")
        
        # 3. High Volume (>100 Trades)
        high_vol = viable[viable['trades'] > 80]
        if not high_vol.empty:
             write_top(high_vol.sort_values("wr", ascending=False).head(10), "TOP 10 HIGH VOLUME (>80 Trades)")

if __name__ == "__main__":
    analyze()
