"""Parse 90-day TradingView reports"""
import pandas as pd

output = []

def log(msg):
    print(msg)
    output.append(str(msg))

def parse_report(filepath, label):
    log(f'\n{"="*80}')
    log(f'{label}')
    log(f'{"="*80}')
    
    xls = pd.ExcelFile(filepath)
    
    # Trades Analysis
    trades_df = pd.read_excel(xls, sheet_name='Trades analysis', header=None)
    log('\n--- TRADES ANALYSIS ---')
    for i, row in trades_df.iterrows():
        if pd.notna(row[0]):
            val1 = row[1] if pd.notna(row[1]) else ''
            val2 = row[2] if len(row) > 2 and pd.notna(row[2]) else ''
            log(f'  {row[0]}: {val1} {val2}')
    
    # List of Trades
    if 'List of trades' in xls.sheet_names:
        trades_list = pd.read_excel(xls, sheet_name='List of trades')
        log(f'\n--- LIST OF TRADES ({len(trades_list)} rows) ---')
        
        # Count actual trades (entries)
        entries = trades_list[trades_list['Type'].str.contains('Entry', na=False)]
        log(f'Entry count: {len(entries)}')
        
        # Calculate stats
        wins = len(entries[entries['Net P&L USD'] > 0])
        losses = len(entries[entries['Net P&L USD'] < 0])
        total_pnl = entries['Net P&L USD'].sum()
        wr = wins / len(entries) * 100 if len(entries) > 0 else 0
        
        log(f'Wins: {wins}, Losses: {losses}')
        log(f'Win Rate: {wr:.1f}%')
        log(f'Total PnL: ${total_pnl:,.0f}')
        
        # Show first and last trades
        log('\nFirst 5 trades:')
        for i, row in entries.head(5).iterrows():
            dt = row['Date/Time']
            tp = row['Type']
            sig = row['Signal']
            pnl = row['Net P&L USD']
            log(f'  {dt} | {tp} | {sig} | PnL: ${pnl:.0f}')
        
        log('\nLast 5 trades:')
        for i, row in entries.tail(5).iterrows():
            dt = row['Date/Time']
            tp = row['Type']
            sig = row['Signal']
            pnl = row['Net P&L USD']
            log(f'  {dt} | {tp} | {sig} | PnL: ${pnl:.0f}')

# New 90-day ES 5m
parse_report(
    r'tradingview/Golden_Protocol_v7.4_[GOD_MODE]_CME_MINI_ES1!_2025-12-24.xlsx',
    'ES 5m (90-day) - The Optimizer'
)

# New 90-day ES 2m
parse_report(
    r'tradingview/Golden_Protocol_v7.4_[GOD_MODE]_CME_MINI_ES1!_2025-12-24 (1).xlsx',
    'ES 2m (90-day) - The Validator'
)

# Save
with open('research/tv_90day_report.txt', 'w') as f:
    f.write('\n'.join(output))
print('\nSaved to research/tv_90day_report.txt')
