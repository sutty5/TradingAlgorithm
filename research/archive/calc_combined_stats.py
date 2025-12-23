
import pandas as pd

def calculate_combined_stats():
    # Manual data input from the analysis_report_phase3.txt results
    # Ideally we load the CSV and filter, but the report has the exact numbers.
    
    # 1. ES SHORT (2m, Trail=True, Targ=0.0, Stop=1.0)
    # wr: 75.93%, pnl: 7843.75, trades: 54
    es_short_pnl = 7843.75
    es_short_trades = 54
    es_short_wins = round(54 * 0.75925926) # 41 wins
    es_short_losses = 54 - es_short_wins # 13 losses
    
    # 2. ES LONG (5m, Trail=True, Targ=0.1, Stop=1.0)
    # wr: 65.00%, pnl: 4111.25, trades: 40
    es_long_pnl = 4111.25
    es_long_trades = 40
    es_long_wins = round(40 * 0.65) # 26 wins
    es_long_losses = 40 - es_long_wins # 14 losses
    
    # 3. NQ LONG (5m, Trail=True, Targ=0.0, Stop=1.0)
    # wr: 71.43%, pnl: 12120.0, trades: 56
    nq_long_pnl = 12120.0
    nq_long_trades = 56
    nq_long_wins = round(56 * 0.71428571) # 40 wins
    nq_long_losses = 56 - nq_long_wins # 16 losses
    
    # 4. NQ SHORT (5m, Trail=True, Targ=0.0, Stop=1.0)
    # wr: 62.50%, pnl: 10152.5, trades: 48
    nq_short_pnl = 10152.5
    nq_short_trades = 48
    nq_short_wins = round(48 * 0.625) # 30 wins
    nq_short_losses = 48 - nq_short_wins # 18 losses
    
    # TOTALS
    total_trades = es_short_trades + es_long_trades + nq_long_trades + nq_short_trades
    total_wins = es_short_wins + es_long_wins + nq_long_wins + nq_short_wins
    total_losses = es_short_losses + es_long_losses + nq_long_losses + nq_short_losses
    total_pnl = es_short_pnl + es_long_pnl + nq_long_pnl + nq_short_pnl
    
    total_wr = (total_wins / total_trades) * 100
    
    avg_pnl_per_trade = total_pnl / total_trades
    
    print("\n--- COMBINED 'GOD MODE' STRATEGY STATS (Phase 3 Validation) ---")
    print(f"Total Trades: {total_trades}")
    print(f"Total Wins:   {total_wins}")
    print(f"Total Losses: {total_losses}")
    print(f"Win Rate:     {total_wr:.2f}%")
    print(f"Net PnL:      ${total_pnl:,.2f}")
    print(f"Avg PnL:      ${avg_pnl_per_trade:.2f} per trade")
    print("\nNote: This validation run covered approx. 17,620 candles (~2 months of recent data Sep-Dec).")

if __name__ == "__main__":
    calculate_combined_stats()
