
import pandas as pd

def read_results():
    try:
        df = pd.read_csv("verification_results.csv")
    except Exception as e:
        print(f"Error: {e}")
        return

    df['is_win'] = df['outcome'] == "WIN"
    
    print("\n--- GOD MODE VERIFIED STATS (DEC 23) ---")
    summary = df.groupby('leg').agg({
        'outcome': 'count',
        'is_win': 'sum',
        'pnl': 'sum'
    })
    
    summary.rename(columns={'outcome': 'Trades', 'is_win': 'Wins', 'pnl': 'PnL'}, inplace=True)
    summary['Win Rate'] = (summary['Wins'] / summary['Trades']) * 100
    summary['Avg PnL'] = summary['PnL'] / summary['Trades']
    
    print(summary)
    
    total_trades = summary['Trades'].sum()
    total_pnl = summary['PnL'].sum()
    total_wins = summary['Wins'].sum()
    
    print(f"\n[AGGREGATE]")
    print(f"Total Trades: {total_trades}")
    print(f"Global WR:    {(total_wins/total_trades)*100:.2f}%")
    print(f"Total PnL:    ${total_pnl:,.2f}")

if __name__ == "__main__":
    read_results()
