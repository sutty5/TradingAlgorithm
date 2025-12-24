"""ES Direct Comparison - Same date range, same logic check"""
import modal
from modal import App, Image, Volume
import sys

APP_NAME = "es-direct-compare"
VOLUME_NAME = "trading-data-vol"
REMOTE_DATA_DIR = "/root/data"
REMOTE_DBN_PATH = f"{REMOTE_DATA_DIR}/trades_es_nq_2025-09-21_2025-12-20.dbn"

image = (
    Image.debian_slim()
    .pip_install("pandas", "numpy", "databento")
    .add_local_dir(".", remote_path="/root/app", ignore=[".git", ".venv", "__pycache__", "data", "tradingview", "output", "*.csv", "*.txt", "*.xlsx"])
)

app = App(APP_NAME)
volume = Volume.from_name(VOLUME_NAME, create_if_missing=True)

@app.function(image=image, volumes={REMOTE_DATA_DIR: volume}, timeout=600, cpu=1.0)
def run_comparison():
    sys.path.append("/root/app")
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
    from data_loader import load_and_prepare_data
    
    output = []
    
    def log(msg):
        print(msg)
        output.append(str(msg))
    
    # =========================================================================
    # ES 5m LONG - Check if we match TradingView trade timestamps
    # =========================================================================
    log("\n" + "="*80)
    log("ES 5m LONG - Nov 28 to Dec 19 (Python data range)")
    log("="*80)
    
    es_data, nq_data = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=5)
    
    # Filter to Nov 28 - Dec 19 (Python data ends Dec 19)
    es_5m = es_data['2025-11-28':'2025-12-19']
    nq_5m = nq_data['2025-11-28':'2025-12-19']
    
    log(f"Date range: {es_5m.index.min()} to {es_5m.index.max()}")
    
    # ES LONG config - matches God Mode spec
    config_5m = BacktestConfig(
        timeframe_minutes=5,
        entry_expiry_candles=10,
        fib_entry=0.5, 
        fib_stop=1.0, 
        fib_target=0.1,  # Extension target
        min_wick_ratio=0.5, 
        max_atr=0.0,
        use_macro_filter=True,
        use_trailing_fib=True
    )
    
    engine = GoldenProtocolBacktest(config_5m)
    res = engine.run(es_5m, nq_5m)
    
    # ES LONG only
    es_long = [t for t in res.trades if t.asset == 'ES' and t.sweep_direction == TradeDirection.LONG and t.state in [TradeState.WIN, TradeState.LOSS]]
    
    log(f"\n=== ES 5m LONG Results ===")
    log(f"Trades: {len(es_long)}")
    log(f"Win Rate: {sum(1 for t in es_long if t.state == TradeState.WIN) / len(es_long) * 100 if es_long else 0:.1f}%")
    
    log(f"\nTradingView found these trades (Nov 28 - Dec 12, within our data range):")
    log(f"  2025-11-28 13:40 - LOSS")
    log(f"  2025-12-01 19:00 - LOSS")
    log(f"  2025-12-03 15:10 - WIN")
    log(f"  2025-12-05 08:25 - LOSS")
    log(f"  2025-12-05 17:00 - LOSS")
    log(f"  2025-12-07 23:05 - LOSS")
    log(f"  2025-12-11 14:45 - LOSS")
    log(f"  2025-12-11 18:25 - WIN")
    log(f"  2025-12-12 00:35 - LOSS")
    
    log(f"\nPython found these trades:")
    for t in es_long:
        log(f"  {t.bos_time} | {t.state.value} | PnL: ${t.pnl:.0f}")
    
    # Check what happened at specific TradingView timestamps
    log(f"\n=== Checking TradingView trade timestamps in Python ===")
    
    # For each TV trade, check if Python had a setup at that time
    tv_trades = [
        ("2025-11-28 13:40:00", "Entry"),
        ("2025-12-03 15:10:00", "Entry"),
    ]
    
    # =========================================================================
    # ES 2m SHORT - Check why Python finds more trades
    # =========================================================================
    log("\n" + "="*80)
    log("ES 2m SHORT - Dec 1 to Dec 19 (Python data range)")
    log("="*80)
    
    es_2m, nq_2m = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=2)
    es_2m = es_2m['2025-12-01':'2025-12-19']
    nq_2m = nq_2m['2025-12-01':'2025-12-19']
    
    log(f"Date range: {es_2m.index.min()} to {es_2m.index.max()}")
    
    # ES SHORT config - matches God Mode spec
    config_2m = BacktestConfig(
        timeframe_minutes=2,
        entry_expiry_candles=15,
        fib_entry=0.5, 
        fib_stop=1.0, 
        fib_target=0.0,
        min_wick_ratio=0.25,
        max_atr=6.0,
        use_macro_filter=True,
        use_trailing_fib=True
    )
    
    engine2 = GoldenProtocolBacktest(config_2m)
    res2 = engine2.run(es_2m, nq_2m)
    
    # ES SHORT only
    es_short = [t for t in res2.trades if t.asset == 'ES' and t.sweep_direction == TradeDirection.SHORT and t.state in [TradeState.WIN, TradeState.LOSS]]
    
    log(f"\n=== ES 2m SHORT Results ===")
    log(f"Trades: {len(es_short)}")
    wins = sum(1 for t in es_short if t.state == TradeState.WIN)
    log(f"Wins: {wins}, Losses: {len(es_short) - wins}")
    log(f"Win Rate: {wins / len(es_short) * 100 if es_short else 0:.1f}%")
    
    log(f"\nTradingView found these trades:")
    log(f"  2025-12-15 16:48 - LOSS (SL)")
    log(f"  2025-12-18 13:08 - LOSS (SL)")
    
    log(f"\nPython found {len(es_short)} trades. First 10:")
    for i, t in enumerate(es_short[:10]):
        log(f"  {t.bos_time} | {t.state.value} | PnL: ${t.pnl:.0f}")
    
    # Check if Dec 15 and Dec 18 are in Python results
    log(f"\n=== Checking if Python found Dec 15-18 trades ===")
    dec_15_trades = [t for t in es_short if t.bos_time and "2025-12-15" in str(t.bos_time)]
    dec_18_trades = [t for t in es_short if t.bos_time and "2025-12-18" in str(t.bos_time)]
    
    log(f"Dec 15 trades: {len(dec_15_trades)}")
    for t in dec_15_trades:
        log(f"  {t.bos_time} | {t.state.value}")
    
    log(f"Dec 18 trades: {len(dec_18_trades)}")
    for t in dec_18_trades:
        log(f"  {t.bos_time} | {t.state.value}")
    
    return output

@app.local_entrypoint()
def main():
    output = run_comparison.remote()
    
    with open("research/es_direct_compare.txt", "w") as f:
        f.write("\n".join(output))
    
    print("\n".join(output[-30:]))
    print("\nFull output saved to research/es_direct_compare.txt")
