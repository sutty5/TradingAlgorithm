"""Get full stats from backtest CSV."""
import pandas as pd

df = pd.read_csv('backtest_trades.csv')

# Basic stats
wins = int((df['state']=='WIN').sum())
losses = int((df['state']=='LOSS').sum())
expired = int((df['state']=='EXPIRED').sum())
pnl = float(df['pnl'].sum())
wr = wins/(wins+losses)*100 if wins+losses>0 else 0

# Max consecutive
filled = df[df['state'].isin(['WIN', 'LOSS'])].copy()
max_cw = max_cl = cw = cl = 0
for s in filled['state']:
    if s == 'WIN':
        cw += 1
        cl = 0
        max_cw = max(max_cw, cw)
    else:
        cl += 1
        cw = 0
        max_cl = max(max_cl, cl)

print('='*60)
print('  GOLDEN PROTOCOL v4.7 - FULL RESULTS')
print('='*60)
print()
print(f'  Total Setups:        {len(df)}')
print(f'  Entry Fills:         {wins+losses}')
print(f'  Expired:             {expired}')
print(f'  Wins:                {wins}')
print(f'  Losses:              {losses}')
print()
print(f'  WIN RATE:            {wr:.1f}%')
print(f'  NET PNL:             ${pnl:,.2f}')
print(f'  Max Consec Wins:     {max_cw}')
print(f'  Max Consec Losses:   {max_cl}')
print()

# Asset breakdown
for asset in ['ES', 'NQ']:
    a = df[df['asset']==asset]
    w = int((a['state']=='WIN').sum())
    l = int((a['state']=='LOSS').sum())
    p = float(a['pnl'].sum())
    r = w/(w+l)*100 if w+l>0 else 0
    print(f'  {asset}: {w}W / {l}L = {r:.1f}% WR, PnL ${p:,.2f}')

# Direction breakdown
print()
for d in ['LONG', 'SHORT']:
    dd = df[df['direction']==d]
    w = int((dd['state']=='WIN').sum())
    l = int((dd['state']=='LOSS').sum())
    p = float(dd['pnl'].sum())
    if w+l > 0:
        r = w/(w+l)*100
        print(f'  {d}: {w}W / {l}L = {r:.1f}% WR, PnL ${p:,.2f}')

print()
print('='*60)
