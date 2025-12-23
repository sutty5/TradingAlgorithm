
import modal
from modal import App, Image, Volume
import sys
import os
import pandas as pd
from dataclasses import dataclass

# --- CONFIGURATION ---
APP_NAME = "god-mode-verifier"
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

@app.function(image=image, volumes={REMOTE_DATA_DIR: volume}, timeout=3600, cpu=1.0)
def run_verification(configs):
    sys.path.append("/root/app")
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
    from data_loader import load_and_prepare_data
    
    # Memoize Data Load
    if not hasattr(run_verification, "data_cache"):
        # We need both 2m and 5m data
        print(f"Loading data from {REMOTE_DBN_PATH}...")
        es_2m, nq_2m = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=2)
        es_5m, nq_5m = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=5)
        run_verification.data_cache = {
            2: (es_2m, nq_2m),
            5: (es_5m, nq_5m)
        }
    
    results = []
    
    for cfg_dict in configs:
        tf = cfg_dict['timeframe_minutes']
        
        # Extract metadata keys that aren't for BacktestConfig
        clean_cfg = cfg_dict.copy()
        leg_name = clean_cfg.pop('name')
        target_asset = clean_cfg.pop('target_asset')
        target_dir_str = clean_cfg.pop('target_dir')
        
        es_data, nq_data = run_verification.data_cache[tf]
        
        bt_config = BacktestConfig(**clean_cfg)
        engine = GoldenProtocolBacktest(bt_config)
        res = engine.run(es_data, nq_data)
        
        for t in res.trades:
            if t.state not in [TradeState.WIN, TradeState.LOSS]: continue
            if t.asset != target_asset: continue
            if t.sweep_direction.value != target_dir_str: continue
            
            results.append({
                "leg": leg_name,
                "outcome": t.outcome,
                "pnl": t.pnl
            })
            
    return results

@app.local_entrypoint()
def main():
    print("🚀 VERIFYING GOD MODE (Phase 3 Baseline)...")
    
    # THE 4 PILLARS OF GOD MODE
    configs = [
        # 1. ES SHORT (2m) - The Validator
        {
            "name": "ES_SHORT_2m",
            "target_asset": "ES", "target_dir": "SHORT",
            "timeframe_minutes": 2,
            "fib_entry": 0.5, "fib_stop": 1.0, "fib_target": 0.0,
            "entry_expiry_candles": 15, "min_wick_ratio": 0.25,
            "max_atr": 6.0, "use_macro_filter": True,
            "entry_mode": "FIB", "use_trailing_fib": True
        },
        # 2. ES LONG (5m) - The Optimizer (Target Extension)
        {
            "name": "ES_LONG_5m",
            "target_asset": "ES", "target_dir": "LONG",
            "timeframe_minutes": 5,
            "fib_entry": 0.5, "fib_stop": 1.0, "fib_target": 0.1, # EXTENSION
            "entry_expiry_candles": 10, "min_wick_ratio": 0.5,
            "max_atr": 0.0, "use_macro_filter": True,
            "entry_mode": "FIB", "use_trailing_fib": True
        },
        # 3. NQ SHORT (5m) - REMOVED (User Request Dec 23 - Low WR)
        # {
        #     "name": "NQ_SHORT_5m",
        #     "target_asset": "NQ", "target_dir": "SHORT",
        #     "timeframe_minutes": 5,
        #     "fib_entry": 0.5, "fib_stop": 1.0, "fib_target": 0.0,
        #     "entry_expiry_candles": 15, "min_wick_ratio": 0.0, # No Filters
        #     "max_atr": 0.0, "use_macro_filter": False,
        #     "entry_mode": "FIB", "use_trailing_fib": True
        # },
        # 4. NQ LONG (5m) - The Banker
        {
            "name": "NQ_LONG_5m",
            "target_asset": "NQ", "target_dir": "LONG",
            "timeframe_minutes": 5,
            "fib_entry": 0.5, "fib_stop": 1.0, "fib_target": 0.0,
            "entry_expiry_candles": 10, "min_wick_ratio": 0.5,
            "max_atr": 0.0, "use_macro_filter": True,
            "entry_mode": "FIB", "use_trailing_fib": True
        }
    ]
    
    # Run
    trades = run_verification.remote(configs)
    
    df = pd.DataFrame(trades)
    df.to_csv("verification_results.csv", index=False)
    df['is_win'] = df['outcome'] == "WIN"
    
    print("\n--- GOD MODE VERIFICATION REPORT ---")
    summary = df.groupby('leg').agg(
        trades=('outcome', 'count'),
        wins=('is_win', 'sum'),
        pnl=('pnl', 'sum')
    )
    summary['win_rate'] = (summary['wins'] / summary['trades']) * 100
    summary['avg_pnl'] = summary['pnl'] / summary['trades']
    
    print(summary)
    
    print("\n[COMBINED TOTALS]")
    total_trades = summary['trades'].sum()
    total_wins = summary['wins'].sum()
    total_pnl = summary['pnl'].sum()
    print(f"Trades: {total_trades}")
    print(f"WR:     {(total_wins/total_trades)*100:.2f}%")
    print(f"PnL:    ${total_pnl:,.2f}")
    
if __name__ == "__main__":
    pass
