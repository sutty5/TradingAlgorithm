"""Quick Dec 1-20 backtest for comparison with TradingView"""
import sys
sys.path.insert(0, '.')
from data_loader import load_and_prepare_data
from backtest_engine import run_backtest, BacktestConfig, TradeState, TradeDirection

# Load data
print("Loading data...")
es_data, nq_data = load_and_prepare_data('data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn', timeframe_minutes=5)

# Filter to Dec 1-20 (our data ends Dec 20)
es_dec = es_data['2025-12-01':'2025-12-20']
nq_dec = nq_data['2025-12-01':'2025-12-20']

print(f'Date range: {nq_dec.index.min()} to {nq_dec.index.max()}')
print(f'Candles: {len(nq_dec)}')

# NQ LONG config (The Banker)
config = BacktestConfig(
    timeframe_minutes=5,
    entry_expiry_candles=10,
    fib_entry=0.5, fib_stop=1.0, fib_target=0.0,
    min_wick_ratio=0.5, max_atr=0.0,
    use_macro_filter=True, use_trailing_fib=True
)

results = run_backtest(es_dec, nq_dec, config)

# Filter to NQ LONG only
nq_long = [t for t in results.trades if t.asset == 'NQ' and t.sweep_direction == TradeDirection.LONG]
wins = sum(1 for t in nq_long if t.state == TradeState.WIN)
losses = sum(1 for t in nq_long if t.state == TradeState.LOSS)
pnl = sum(t.pnl for t in nq_long)
wr = wins/(wins+losses)*100 if (wins+losses) > 0 else 0

print(f'\nNQ LONG 5m (Dec 1-20):')
print(f'  Trades: {wins+losses}')
print(f'  Wins: {wins}, Losses: {losses}')
print(f'  Win Rate: {wr:.1f}%')
print(f'  PnL: ${pnl:,.0f}')

# Print individual trades
print("\nTrade details:")
for t in nq_long:
    if t.state in [TradeState.WIN, TradeState.LOSS]:
        print(f"  {t.bos_time} | {t.state.value} | Entry: {t.entry_price:.2f} | PnL: ${t.pnl:.0f}")
