"""Parse TradingView Excel reports and save to file"""
import pandas as pd

output = []

def log(msg):
    print(msg)
    output.append(msg)

def parse_report(filepath, label):
    log(f"\n{'='*80}")
    log(f"{label}")
    log(f"{'='*80}")
    
    xls = pd.ExcelFile(filepath)
    
    # Trades Analysis
    trades_df = pd.read_excel(xls, sheet_name='Trades analysis', header=None)
    log("\n--- TRADES ANALYSIS ---")
    for i, row in trades_df.iterrows():
        if pd.notna(row[0]):
            val1 = row[1] if pd.notna(row[1]) else ""
            val2 = row[2] if len(row) > 2 and pd.notna(row[2]) else ""
            log(f"  {row[0]}: {val1} {val2}")
    
    # List of Trades
    if 'List of trades' in xls.sheet_names:
        trades_list = pd.read_excel(xls, sheet_name='List of trades')
        log(f"\n--- LIST OF TRADES ({len(trades_list)} trades) ---")
        for i, row in trades_list.iterrows():
            log(str(row.to_dict()))

# ES 5m
parse_report(
    r'tradingview/Golden_Protocol_v7.4_[GOD_MODE]_CME_MINI_ES1!_2025-12-23.xlsx',
    'ES 5m (The Optimizer)'
)

# ES 2m
parse_report(
    r'tradingview/Golden_Protocol_v7.4_[GOD_MODE]_CME_MINI_ES1!_2025-12-23 (1).xlsx',
    'ES 2m (The Validator)'
)

# Save to file
with open('research/tv_report_summary.txt', 'w') as f:
    f.write('\n'.join(output))
print("\nSaved to research/tv_report_summary.txt")
