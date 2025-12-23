"""ES Long 5m - Nov 28 to Dec 20 - NO MACRO FILTER"""
import modal
from modal import App, Image, Volume
import sys

APP_NAME = "es-no-macro"
VOLUME_NAME = "trading-data-vol"
REMOTE_DATA_DIR = "/root/data"
REMOTE_DBN_PATH = f"{REMOTE_DATA_DIR}/trades_es_nq_2025-09-21_2025-12-20.dbn"

image = (
    Image.debian_slim()
    .pip_install("pandas", "numpy", "databento")
    .add_local_dir(".", remote_path="/root/app", ignore=[".git", ".venv", "__pycache__", "data", "tradingview", "output", "*.csv", "*.txt"])
)

app = App(APP_NAME)
volume = Volume.from_name(VOLUME_NAME, create_if_missing=True)

@app.function(image=image, volumes={REMOTE_DATA_DIR: volume}, timeout=600, cpu=1.0)
def run_test():
    sys.path.append("/root/app")
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
    from data_loader import load_and_prepare_data
    
    print("Loading data...")
    es_data, nq_data = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=5)
    
    # Filter to Nov 28 - Dec 20
    es_data = es_data['2025-11-28':'2025-12-20']
    nq_data = nq_data['2025-11-28':'2025-12-20']
    
    print(f"Date range: {es_data.index.min()} to {es_data.index.max()}")
    
    # ES LONG config WITHOUT macro filter
    config = BacktestConfig(
        timeframe_minutes=5,
        entry_expiry_candles=10,
        fib_entry=0.5, fib_stop=1.0, fib_target=0.1,
        min_wick_ratio=0.5, max_atr=0.0,
        use_macro_filter=False,  # DISABLED
        use_trailing_fib=True
    )
    
    engine = GoldenProtocolBacktest(config)
    results = engine.run(es_data, nq_data)
    
    # ES LONG only
    es_long = [t for t in results.trades if t.asset == 'ES' and t.sweep_direction == TradeDirection.LONG and t.state in [TradeState.WIN, TradeState.LOSS]]
    
    wins = sum(1 for t in es_long if t.state == TradeState.WIN)
    losses = len(es_long) - wins
    pnl = sum(t.pnl for t in es_long)
    wr = wins / len(es_long) * 100 if es_long else 0
    
    print(f"\n{'='*60}")
    print(f"  ES LONG 5m (Nov 28 - Dec 20) - NO MACRO FILTER")
    print(f"{'='*60}")
    print(f"  Trades: {len(es_long)}")
    print(f"  Wins: {wins}, Losses: {losses}")
    print(f"  Win Rate: {wr:.1f}%")
    print(f"  PnL: ${pnl:,.0f}")
    print(f"{'='*60}")
    
    for t in es_long:
        print(f"  {t.bos_time} | {t.state.value} | Entry: {t.entry_price:.2f} | PnL: ${t.pnl:.0f}")
    
    return {"trades": len(es_long), "wins": wins, "wr": wr, "pnl": pnl}

@app.local_entrypoint()
def main():
    result = run_test.remote()
    print(f"\nResult: {result}")
    with open("es_no_macro_result.txt", "w") as f:
        f.write(str(result))
