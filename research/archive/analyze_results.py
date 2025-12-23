"""Analyze backtest results from CSV."""
import pandas as pd

df = pd.read_csv('backtest_trades.csv')

# Basic stats
wins = (df['state']=='WIN').sum()
losses = (df['state']=='LOSS').sum()
expired = (df['state']=='EXPIRED').sum()
pnl = df['pnl'].sum()
wr = wins/(wins+losses)*100 if wins+losses>0 else 0

# Max consecutive
filled = df[df['state'].isin(['WIN', 'LOSS'])].copy()
filled['is_win'] = filled['state'] == 'WIN'
max_consec_wins = 0
max_consec_losses = 0
curr_wins = 0
curr_losses = 0
for is_win in filled['is_win']:
    if is_win:
        curr_wins += 1
        curr_losses = 0
        max_consec_wins = max(max_consec_wins, curr_wins)
    else:
        curr_losses += 1
        curr_wins = 0
        max_consec_losses = max(max_consec_losses, curr_losses)

print('='*60)
print('  GOLDEN PROTOCOL v4.7 BACKTEST RESULTS')
print('='*60)
print()
print('[TRADE STATISTICS]')
print(f'  Total Setups:      {len(df):,}')
print(f'  Entry Fills:       {wins+losses:,}')
print(f'  Expired (no fill): {expired:,}')
print(f'  Wins:              {wins:,}')
print(f'  Losses:            {losses:,}')
print()
print('[PERFORMANCE]')
print(f'  Win Rate:              {wr:.1f}%')
print(f'  Net PnL:               ${pnl:,.2f}')
print(f'  Max Consecutive Wins:  {max_consec_wins}')
print(f'  Max Consecutive Losses:{max_consec_losses}')
print()

# By asset
print('[BY ASSET]')
for asset in ['ES', 'NQ']:
    a = df[df['asset']==asset]
    w = (a['state']=='WIN').sum()
    l = (a['state']=='LOSS').sum()
    p = a['pnl'].sum()
    rt = w/(w+l)*100 if w+l>0 else 0
    print(f'  {asset}: {w} W / {l} L = {rt:.1f}% Win Rate, PnL: ${p:,.2f}')

# By direction  
print()
print('[BY DIRECTION]')
for d in ['LONG', 'SHORT']:
    dd = df[df['direction']==d]
    w = (dd['state']=='WIN').sum()
    l = (dd['state']=='LOSS').sum()
    p = dd['pnl'].sum()
    if w+l > 0:
        rt = w/(w+l)*100
        print(f'  {d}: {w} W / {l} L = {rt:.1f}% Win Rate, PnL: ${p:,.2f}')

print()
print('='*60)

# Sample some trades
print()
print('[SAMPLE TRADES]')
print(df[['ppi_time', 'asset', 'direction', 'entry_price', 'target_price', 'stop_price', 'state', 'pnl']].head(10).to_string())
