import pandas as pd
xl = pd.ExcelFile('tradingview/Golden_Protocol_v7.2_[GOD_MODE]_CME_MINI_NQ1!_2025-12-23.xlsx')
df = pd.read_excel(xl, sheet_name='List of trades')

lines = []
lines.append('Columns: ' + str(list(df.columns)))
lines.append('')
lines.append('Trade dates and types:')
for i, row in df.iterrows():
    trade_num = row["Trade #"]
    trade_type = row["Type"]
    dt = row["Date/Time"]
    signal = str(row["Signal"])[:30] if pd.notna(row["Signal"]) else ""
    price = row["Price USD"]
    lines.append(f'{trade_num:3} | {trade_type:15} | {dt} | {signal:30} | {price}')

with open('research/tv_trades_output.txt', 'w') as f:
    f.write('\n'.join(lines))
print(f'Wrote {len(df)} rows to research/tv_trades_output.txt')
