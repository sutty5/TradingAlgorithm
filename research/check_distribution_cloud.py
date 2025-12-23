"""Check ES Long 5m trade distribution"""
import modal
from modal import App, Image, Volume
import sys
import pandas as pd

APP_NAME = "trade-distribution"
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
def check_distribution():
    sys.path.append("/root/app")
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
    from data_loader import load_and_prepare_data
    import pandas as pd
    
    print(f"Loading data...")
    es_data, nq_data = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=5)
    
    # ES LONG config
    config = BacktestConfig(
        timeframe_minutes=5,
        entry_expiry_candles=10,
        fib_entry=0.5, fib_stop=1.0, fib_target=0.1,
        min_wick_ratio=0.5, max_atr=0.0,
        use_macro_filter=True, use_trailing_fib=True
    )
    
    engine = GoldenProtocolBacktest(config)
    results = engine.run(es_data, nq_data)
    
    # Get ES LONG trades only
    es_long = [t for t in results.trades if t.asset == 'ES' and t.sweep_direction == TradeDirection.LONG and t.state in [TradeState.WIN, TradeState.LOSS]]
    
    print(f"\nES LONG 5m Trade Distribution:")
    print("-" * 60)
    
    # Group by month
    trade_dates = {}
    for t in es_long:
        month = t.bos_time.strftime("%Y-%m")
        if month not in trade_dates:
            trade_dates[month] = []
        trade_dates[month].append(t)
    
    for month in sorted(trade_dates.keys()):
        trades = trade_dates[month]
        wins = sum(1 for t in trades if t.state == TradeState.WIN)
        pnl = sum(t.pnl for t in trades)
        print(f"  {month}: {len(trades)} trades, {wins} wins ({wins/len(trades)*100:.0f}% WR), PnL: ${pnl:.0f}")
    
    print("\nRecent trades (last 10):")
    for t in es_long[-10:]:
        print(f"  {t.bos_time} | {t.state.value} | Entry: {t.entry_price:.2f}")
    
    return {}

@app.local_entrypoint()
def main():
    check_distribution.remote()
