"""
Golden Protocol v4.8 R&D - Phase 1: Data Analysis & Pattern Discovery

Analyze the existing backtest trades to find patterns that could improve win rate.
"""
import pandas as pd
import numpy as np
from datetime import datetime

# Load trade data
df = pd.read_csv('backtest_trades.csv')

# Parse timestamps
df['ppi_time'] = pd.to_datetime(df['ppi_time'])
df['fill_time'] = pd.to_datetime(df['fill_time'])
df['outcome_time'] = pd.to_datetime(df['outcome_time'])

# Filter to filled trades only (exclude expired)
filled = df[df['state'].isin(['WIN', 'LOSS'])].copy()
filled['is_win'] = filled['state'] == 'WIN'

# Extract time features
filled['hour'] = filled['ppi_time'].dt.hour
filled['day_of_week'] = filled['ppi_time'].dt.dayofweek  # 0=Monday
filled['day_name'] = filled['ppi_time'].dt.day_name()

# Calculate range size
filled['range_size'] = abs(filled['stop_price'] - filled['target_price'])

print('='*70)
print('  GOLDEN PROTOCOL v4.8 R&D - PATTERN ANALYSIS')
print('='*70)
print()

# ============================================================
# 1. HOURLY ANALYSIS
# ============================================================
print('[1] HOURLY PERFORMANCE (UTC)')
print('-'*70)
hourly = filled.groupby('hour').agg({
    'is_win': ['sum', 'count', 'mean'],
    'pnl': 'sum'
}).round(2)
hourly.columns = ['wins', 'total', 'win_rate', 'pnl']
hourly['losses'] = hourly['total'] - hourly['wins']
hourly = hourly[['wins', 'losses', 'total', 'win_rate', 'pnl']]
hourly['win_rate'] = (hourly['win_rate'] * 100).round(1)

# Sort by win rate
hourly_sorted = hourly.sort_values('win_rate', ascending=False)
print(hourly_sorted.to_string())

# Best and worst hours
best_hours = hourly_sorted[hourly_sorted['total'] >= 5].head(5)
worst_hours = hourly_sorted[hourly_sorted['total'] >= 5].tail(5)
print()
print(f'BEST HOURS (>=5 trades): {list(best_hours.index)}')
print(f'WORST HOURS (>=5 trades): {list(worst_hours.index)}')

# ============================================================
# 2. DAY OF WEEK ANALYSIS
# ============================================================
print()
print('[2] DAY OF WEEK PERFORMANCE')
print('-'*70)
daily = filled.groupby('day_name').agg({
    'is_win': ['sum', 'count', 'mean'],
    'pnl': 'sum'
}).round(2)
daily.columns = ['wins', 'total', 'win_rate', 'pnl']
daily['win_rate'] = (daily['win_rate'] * 100).round(1)
print(daily.to_string())

# ============================================================
# 3. DIRECTION ANALYSIS
# ============================================================
print()
print('[3] DIRECTION PERFORMANCE')
print('-'*70)
direction = filled.groupby('direction').agg({
    'is_win': ['sum', 'count', 'mean'],
    'pnl': 'sum'
}).round(2)
direction.columns = ['wins', 'total', 'win_rate', 'pnl']
direction['win_rate'] = (direction['win_rate'] * 100).round(1)
print(direction.to_string())

# ============================================================
# 4. ASSET ANALYSIS  
# ============================================================
print()
print('[4] ASSET PERFORMANCE')
print('-'*70)
asset = filled.groupby('asset').agg({
    'is_win': ['sum', 'count', 'mean'],
    'pnl': 'sum'
}).round(2)
asset.columns = ['wins', 'total', 'win_rate', 'pnl']
asset['win_rate'] = (asset['win_rate'] * 100).round(1)
print(asset.to_string())

# ============================================================
# 5. RANGE SIZE ANALYSIS (Quantiles)
# ============================================================
print()
print('[5] RANGE SIZE ANALYSIS')
print('-'*70)

# Create range size buckets
filled['range_bucket'] = pd.qcut(filled['range_size'], q=5, labels=['Tiny', 'Small', 'Medium', 'Large', 'Huge'])
range_perf = filled.groupby('range_bucket').agg({
    'is_win': ['sum', 'count', 'mean'],
    'pnl': 'sum',
    'range_size': ['min', 'max']
}).round(2)
range_perf.columns = ['wins', 'total', 'win_rate', 'pnl', 'min_range', 'max_range']
range_perf['win_rate'] = (range_perf['win_rate'] * 100).round(1)
print(range_perf.to_string())

# ============================================================
# 6. COMBINED FILTERS ANALYSIS
# ============================================================
print()
print('[6] COMBINED FILTERS - FINDING SWEET SPOTS')
print('-'*70)

# SHORT only during certain hours
short_only = filled[filled['direction'] == 'SHORT']
short_hourly = short_only.groupby('hour').agg({
    'is_win': ['sum', 'count', 'mean'],
    'pnl': 'sum'
}).round(2)
short_hourly.columns = ['wins', 'total', 'win_rate', 'pnl']
short_hourly['win_rate'] = (short_hourly['win_rate'] * 100).round(1)
best_short_hours = short_hourly[short_hourly['total'] >= 3].sort_values('win_rate', ascending=False)
print('SHORT trades by hour (>=3 trades):')
print(best_short_hours.head(10).to_string())

# Asset + Direction combinations
print()
print('Asset + Direction combinations:')
combo = filled.groupby(['asset', 'direction']).agg({
    'is_win': ['sum', 'count', 'mean'],
    'pnl': 'sum'
}).round(2)
combo.columns = ['wins', 'total', 'win_rate', 'pnl']
combo['win_rate'] = (combo['win_rate'] * 100).round(1)
print(combo.to_string())

# ============================================================
# 7. SESSION ANALYSIS (Trading Sessions)
# ============================================================
print()
print('[7] TRADING SESSION ANALYSIS')
print('-'*70)

def get_session(hour):
    # UTC hours
    if 22 <= hour or hour < 6:  # Asia session (approx)
        return 'Asia'
    elif 6 <= hour < 13:  # London session
        return 'London'
    elif 13 <= hour < 20:  # New York session
        return 'New York'
    else:
        return 'After Hours'

filled['session'] = filled['hour'].apply(get_session)
session = filled.groupby('session').agg({
    'is_win': ['sum', 'count', 'mean'],
    'pnl': 'sum'
}).round(2)
session.columns = ['wins', 'total', 'win_rate', 'pnl']
session['win_rate'] = (session['win_rate'] * 100).round(1)
print(session.to_string())

# ============================================================
# 8. LOSING TRADE PATTERNS
# ============================================================
print()
print('[8] LOSING TRADE PATTERNS')
print('-'*70)
losses = filled[filled['state'] == 'LOSS']
print(f'Total losses: {len(losses)}')
print(f'Loss by direction: LONG={len(losses[losses["direction"]=="LONG"])}, SHORT={len(losses[losses["direction"]=="SHORT"])}')
print(f'Loss by asset: ES={len(losses[losses["asset"]=="ES"])}, NQ={len(losses[losses["asset"]=="NQ"])}')

# Worst hours for losses
loss_hours = losses.groupby('hour').size().sort_values(ascending=False)
print(f'Hours with most losses: {list(loss_hours.head(5).index)}')

# ============================================================
# SUMMARY - OPTIMIZATION RECOMMENDATIONS
# ============================================================
print()
print('='*70)
print('  OPTIMIZATION RECOMMENDATIONS')
print('='*70)

# Calculate improvement potential
short_wr = direction.loc['SHORT', 'win_rate'] if 'SHORT' in direction.index else 0
long_wr = direction.loc['LONG', 'win_rate'] if 'LONG' in direction.index else 0

print()
print(f'1. DIRECTION: SHORT ({short_wr}%) outperforms LONG ({long_wr}%)')
print(f'   -> Consider SHORT-only or reduced LONG exposure')
print()
print(f'2. BEST HOURS: {list(best_hours.head(3).index)}')
print(f'   -> Consider time-based filtering')
print()
print(f'3. WORST HOURS: {list(worst_hours.head(3).index)}')
print(f'   -> Consider blocking these hours')
print()

# Save analysis for optimizer
analysis = {
    'best_hours': list(best_hours.head(5).index),
    'worst_hours': list(worst_hours.tail(5).index),
    'best_direction': 'SHORT' if short_wr > long_wr else 'LONG',
    'session_performance': session.to_dict()
}
print('Analysis complete. Ready for Phase 2 optimization.')
