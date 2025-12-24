"""ES Comparison - Run Python backtest for same period as TradingView"""
import modal
from modal import App, Image, Volume
import sys
import json

APP_NAME = "es-comparison-v2"
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
    results = {}
    
    def log(msg):
        print(msg)
        output.append(str(msg))
    
    # =========================================================================
    # ES 5m LONG - The Optimizer
    # =========================================================================
    log("\n" + "="*80)
    log("ES 5m LONG (The Optimizer) - WITH Macro Filter")
    log("="*80)
    
    es_data, nq_data = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=5)
    
    # Filter to Nov 28 - Dec 23 (matching TradingView date range)
    es_5m = es_data['2025-11-28':'2025-12-23']
    nq_5m = nq_data['2025-11-28':'2025-12-23']
    
    log(f"Date range: {es_5m.index.min()} to {es_5m.index.max()}")
    log(f"Candles: {len(es_5m)}")
    
    # ES LONG config WITH macro filter (matches God Mode spec)
    config_5m = BacktestConfig(
        timeframe_minutes=5,
        entry_expiry_candles=10,
        fib_entry=0.5, 
        fib_stop=1.0, 
        fib_target=0.1,  # Extension target!
        min_wick_ratio=0.5, 
        max_atr=0.0,
        use_macro_filter=True,  # ENABLED
        use_trailing_fib=True
    )
    
    engine = GoldenProtocolBacktest(config_5m)
    res = engine.run(es_5m, nq_5m)
    
    # ES LONG only
    es_long = [t for t in res.trades if t.asset == 'ES' and t.sweep_direction == TradeDirection.LONG and t.state in [TradeState.WIN, TradeState.LOSS]]
    
    wins = sum(1 for t in es_long if t.state == TradeState.WIN)
    losses = len(es_long) - wins
    pnl = sum(t.pnl for t in es_long)
    wr = wins / len(es_long) * 100 if es_long else 0
    
    log(f"\nRESULTS (ES 5m LONG WITH Macro):")
    log(f"  Trades: {len(es_long)}")
    log(f"  Wins: {wins}, Losses: {losses}")
    log(f"  Win Rate: {wr:.1f}%")
    log(f"  PnL: ${pnl:,.0f}")
    
    log(f"\nTRADE DETAILS:")
    for t in es_long:
        log(f"  {t.bos_time} | {t.state.value} | Entry: {t.entry_price:.2f} | Target: {t.target_price:.2f} | PnL: ${t.pnl:.0f}")
    
    results['es_5m_with_macro'] = {"trades": len(es_long), "wins": wins, "wr": wr, "pnl": pnl}
    
    # =========================================================================
    # ES 2m SHORT - The Validator
    # =========================================================================
    log("\n" + "="*80)
    log("ES 2m SHORT (The Validator) - WITH Macro Filter")
    log("="*80)
    
    es_data_2m, nq_data_2m = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=2)
    
    # Filter to Dec 1 - Dec 23 (same rough period)
    es_2m = es_data_2m['2025-12-01':'2025-12-23']
    nq_2m = nq_data_2m['2025-12-01':'2025-12-23']
    
    log(f"Date range: {es_2m.index.min()} to {es_2m.index.max()}")
    log(f"Candles: {len(es_2m)}")
    
    # ES SHORT config (matches God Mode spec)
    config_2m = BacktestConfig(
        timeframe_minutes=2,
        entry_expiry_candles=15,  # 15 candles for shorts
        fib_entry=0.5, 
        fib_stop=1.0, 
        fib_target=0.0,
        min_wick_ratio=0.25,  # Lower wick requirement
        max_atr=6.0,  # ATR filter
        use_macro_filter=True,
        use_trailing_fib=True
    )
    
    engine2 = GoldenProtocolBacktest(config_2m)
    res2 = engine2.run(es_2m, nq_2m)
    
    # ES SHORT only
    es_short = [t for t in res2.trades if t.asset == 'ES' and t.sweep_direction == TradeDirection.SHORT and t.state in [TradeState.WIN, TradeState.LOSS]]
    
    wins2 = sum(1 for t in es_short if t.state == TradeState.WIN)
    losses2 = len(es_short) - wins2
    pnl2 = sum(t.pnl for t in es_short)
    wr2 = wins2 / len(es_short) * 100 if es_short else 0
    
    log(f"\nRESULTS (ES 2m SHORT WITH Macro):")
    log(f"  Trades: {len(es_short)}")
    log(f"  Wins: {wins2}, Losses: {losses2}")
    log(f"  Win Rate: {wr2:.1f}%")
    log(f"  PnL: ${pnl2:,.0f}")
    
    log(f"\nTRADE DETAILS:")
    for t in es_short:
        log(f"  {t.bos_time} | {t.state.value} | Entry: {t.entry_price:.2f} | Target: {t.target_price:.2f} | PnL: ${t.pnl:.0f}")
    
    results['es_2m_with_macro'] = {"trades": len(es_short), "wins": wins2, "wr": wr2, "pnl": pnl2}
    
    return {
        "results": results,
        "output": output
    }

@app.local_entrypoint()
def main():
    result = run_comparison.remote()
    
    # Save to file
    with open("research/es_comparison_output.txt", "w") as f:
        f.write("\n".join(result["output"]))
    
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    for k, v in result["results"].items():
        print(f"{k}: {v}")
    
    print("\nFull output saved to research/es_comparison_output.txt")
