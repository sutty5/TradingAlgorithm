
import modal
import pandas as pd
import sys
import os
from modal import App, Image, Volume
from datetime import datetime

# --- CONFIGURATION ---
APP_NAME = "golden-protocol-forensics"
VOLUME_NAME = "trading-data-vol"
DBN_FILENAME = "trades_es_nq_2025-09-21_2025-12-20.dbn"
REMOTE_DATA_DIR = "/root/data"
REMOTE_DBN_PATH = f"{REMOTE_DATA_DIR}/{DBN_FILENAME}"

# --- IMAGE DEFINITION ---
image = (
    Image.debian_slim()
    .pip_install("pandas", "numpy", "databento")
    .add_local_dir(
        ".",
        remote_path="/root/app",
        ignore=[".git", ".venv", "__pycache__", "data", "tradingview", "output", "*.csv"]
    )
)

app = App(APP_NAME)
volume = Volume.from_name(VOLUME_NAME, create_if_missing=True)

@app.function(
    image=image, 
    volumes={REMOTE_DATA_DIR: volume}, 
    timeout=3600, 
    cpu=2.0,
    memory=4096 
)
def run_forensics_remote():
    sys.path.append("/root/app")
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState
    from data_loader import load_and_prepare_data
    
    print("Remote: Loading Data...")
    # Load 5m data (covers mostly everything needed for now, or load 2m AND 5m?)
    # Validated Legs:
    # ES Short: 2m
    # NQ Long: 5m
    # We need to run two separate loads or one load and resample?
    # data_loader creates 1m bars then resamples.
    # We can run distinct backtests.
    
    configs = [
        {
            "name": "ES_SHORT_2m_GOD",
            "tf": 2,
            "cfg": BacktestConfig(
                timeframe_minutes=2,
                entry_mode="FIB",
                use_trailing_fib=True,
                fib_entry=0.5,
                fib_stop=1.0,
                fib_target=0.0,
                entry_expiry_candles=15,
                min_wick_ratio=0.25,
                max_atr=6.0,
                use_macro_filter=True
            )
        },
        {
            "name": "NQ_LONG_5m_GOD",
            "tf": 5,
            "cfg": BacktestConfig(
                timeframe_minutes=5,
                entry_mode="FIB",
                use_trailing_fib=True,
                fib_entry=0.5,
                fib_stop=1.0, 
                fib_target=0.0,
                entry_expiry_candles=10,
                min_wick_ratio=0.5,
                use_macro_filter=True
            )
        }
    ]
    
    all_trades = []
    
    # 1. Load 2m Data first
    print("Remote: Loading 2m Data for ES...")
    es_2m, nq_2m = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=2)
    
    # Run ES Short 2m
    c = configs[0] # ES Short
    print(f"Remote: Running {c['name']}...")
    engine = GoldenProtocolBacktest(c['cfg'])
    res = engine.run(es_2m, nq_2m)
    
    for t in res.trades:
        if t.state not in [TradeState.WIN, TradeState.LOSS]: continue
        if t.asset != "ES": continue
        if t.sweep_direction.value != "SHORT": continue
        
        # Get context
        try:
            candle = es_2m.loc[t.ppi_time]
            all_trades.append({
                "strategy": c['name'], "asset": "ES", "direction": "SHORT",
                "outcome": t.outcome, "pnl": t.pnl, "ppi_time": t.ppi_time,
                "hour": t.ppi_time.hour, "atr": candle.get('atr_14', 0),
                "rvol": candle.get('rvol', 0), "wick": candle.get('wick_ratio_up', 0)
            })
        except: pass

    # Clear memory
    del es_2m, nq_2m, res, engine
    
    # 2. Load 5m Data
    print("Remote: Loading 5m Data for NQ...")
    es_5m, nq_5m = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=5)
    
    # Run NQ Long 5m
    c = configs[1] # NQ Long
    print(f"Remote: Running {c['name']}...")
    engine = GoldenProtocolBacktest(c['cfg'])
    res = engine.run(es_5m, nq_5m)
    
    for t in res.trades:
        if t.state not in [TradeState.WIN, TradeState.LOSS]: continue
        if t.asset != "NQ": continue
        if t.sweep_direction.value != "LONG": continue
        
        try:
            candle = nq_5m.loc[t.ppi_time]
            all_trades.append({
                "strategy": c['name'], "asset": "NQ", "direction": "LONG",
                "outcome": t.outcome, "pnl": t.pnl, "ppi_time": t.ppi_time,
                "hour": t.ppi_time.hour, "atr": candle.get('atr_14', 0),
                "rvol": candle.get('rvol', 0), "wick": candle.get('wick_ratio_down', 0)
            })
        except: pass
        
    return all_trades

@app.local_entrypoint()
def main():
    print("🚀 Launching Cloud Forensics...")
    trades = run_forensics_remote.remote()
    print(f"✅ Received {len(trades)} trades from cloud.")
    
    df = pd.DataFrame(trades)
    df.to_csv("forensic_trades_cloud.csv", index=False)
    
    # Analysis
    print("\n--- FORENSIC ANALYSIS (CLOUD RESULTS) ---")
    df['is_loss'] = df['outcome'] == "LOSS"
    
    print("\n[Win Rate by Hour]")
    hourly = df.groupby('hour')['is_loss'].agg(['count', 'mean'])
    hourly['win_rate'] = (1 - hourly['mean']) * 100
    print(hourly)
    
    print("\n[Win Rate by ATR]")
    try:
        df['atr_bin'] = pd.qcut(df['atr'], 5)
        print(df.groupby('atr_bin', observed=False)['is_loss'].agg(['count', 'mean', lambda x: (1-x.mean())*100]))
    except: pass

