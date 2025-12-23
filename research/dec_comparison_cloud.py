"""
Cloud backtest for Dec 1-20 to compare with TradingView results
"""
import modal
from modal import App, Image, Volume
import sys
import pandas as pd

APP_NAME = "dec-comparison"
VOLUME_NAME = "trading-data-vol"
DBN_FILENAME = "trades_es_nq_2025-09-21_2025-12-20.dbn"
REMOTE_DATA_DIR = "/root/data"
REMOTE_DBN_PATH = f"{REMOTE_DATA_DIR}/{DBN_FILENAME}"

image = (
    Image.debian_slim()
    .pip_install("pandas", "numpy", "databento")
    .add_local_dir(
        ".",
        remote_path="/root/app",
        ignore=[".git", ".venv", "__pycache__", "data", "tradingview", "output", "*.csv", "*.txt"]
    )
)

app = App(APP_NAME)
volume = Volume.from_name(VOLUME_NAME, create_if_missing=True)

@app.function(image=image, volumes={REMOTE_DATA_DIR: volume}, timeout=600, cpu=1.0)
def run_dec_backtest():
    sys.path.append("/root/app")
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
    from data_loader import load_and_prepare_data
    
    print(f"Loading data from {REMOTE_DBN_PATH}...")
    es_data, nq_data = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=5)
    
    # Filter to Dec 1-20
    es_dec = es_data['2025-12-01':'2025-12-20']
    nq_dec = nq_data['2025-12-01':'2025-12-20']
    
    print(f"Dec range: {nq_dec.index.min()} to {nq_dec.index.max()}")
    print(f"Candles: {len(nq_dec)}")
    
    # NQ LONG config (The Banker)
    config = BacktestConfig(
        timeframe_minutes=5,
        entry_expiry_candles=10,
        fib_entry=0.5, fib_stop=1.0, fib_target=0.0,
        min_wick_ratio=0.5, max_atr=0.0,
        use_macro_filter=True, use_trailing_fib=True
    )
    
    engine = GoldenProtocolBacktest(config)
    results = engine.run(es_dec, nq_dec)
    
    # Filter to NQ LONG only
    nq_long = [t for t in results.trades if t.asset == 'NQ' and t.sweep_direction == TradeDirection.LONG]
    wins = sum(1 for t in nq_long if t.state == TradeState.WIN)
    losses = sum(1 for t in nq_long if t.state == TradeState.LOSS)
    pnl = sum(t.pnl for t in nq_long)
    
    # Collect trade details
    trades = []
    for t in nq_long:
        if t.state in [TradeState.WIN, TradeState.LOSS]:
            trades.append({
                "bos_time": str(t.bos_time),
                "outcome": t.state.value,
                "entry": t.entry_price,
                "stop": t.stop_price,
                "target": t.target_price,
                "pnl": t.pnl
            })
    
    return {
        "wins": wins,
        "losses": losses,
        "pnl": pnl,
        "trades": trades
    }

@app.local_entrypoint()
def main():
    print("🚀 Running Dec 1-20 comparison backtest on cloud...")
    
    result = run_dec_backtest.remote()
    
    wins = result["wins"]
    losses = result["losses"]
    pnl = result["pnl"]
    trades = result["trades"]
    
    total = wins + losses
    wr = (wins / total * 100) if total > 0 else 0
    
    output = []
    output.append("=" * 60)
    output.append("  NQ LONG 5m (Dec 1-20) - Python Engine")
    output.append("=" * 60)
    output.append(f"  Trades: {total}")
    output.append(f"  Wins: {wins}, Losses: {losses}")
    output.append(f"  Win Rate: {wr:.1f}%")
    output.append(f"  PnL: ${pnl:,.0f}")
    output.append("=" * 60)
    output.append("")
    output.append("Trade Details:")
    for t in trades:
        output.append(f"  {t['bos_time']} | {t['outcome']} | Entry: {t['entry']:.2f} | PnL: ${t['pnl']:.0f}")
    
    # Print and save
    for line in output:
        print(line)
    
    with open("dec_comparison_results.txt", "w") as f:
        f.write("\n".join(output))
