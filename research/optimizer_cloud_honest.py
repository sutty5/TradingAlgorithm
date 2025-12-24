import modal
from modal import App, Image, Volume
import sys
import os
import itertools
from dataclasses import dataclass
import pandas as pd
import numpy as np
import databento as db

# --- CONFIGURATION ---
APP_NAME = "golden-protocol-honest-opt"
VOLUME_NAME = "trading-data-vol"
# Using the 90-day file as requested
DBN_FILENAME = "trades_es_nq_2025-09-21_2025-12-20.dbn" 
REMOTE_DATA_DIR = "/root/data"
REMOTE_DBN_PATH = f"{REMOTE_DATA_DIR}/{DBN_FILENAME}"

# --- IMAGE DEFINITION ---
image = (
    Image.debian_slim()
    # Install dependencies
    .pip_install("pandas", "numpy", "databento")
    # Add Backtest Engine (Verified to work via mount)
    .add_local_file(
        "backtest_engine.py",
        remote_path="/root/app/backtest_engine.py"
    )
)

app = App(APP_NAME)
volume = Volume.from_name(VOLUME_NAME, create_if_missing=True)

# --- HONEST DATA LOADER (Inlined to force correct logic) ---
def honest_loader(filepath, timeframe_minutes=2):
    print(f"Loading HONEST data from {filepath} (Timeframe: {timeframe_minutes}m)")
    
    # 1. READ RAW
    store = db.DBNStore.from_file(filepath)
    raw_df = store.to_df()
    
    def filter_sym(df, p):
        if 'symbol' in df.columns: return df[df['symbol'].str.startswith(p)].copy()
        if df.index.names and 'symbol' in df.index.names: return df.reset_index()[df.reset_index()['symbol'].str.startswith(p)].copy()
        for c in df.columns:
            if 'symbol' in c.lower(): return df[df[c].str.startswith(p)].copy()
        return pd.DataFrame()

    def agg_ohlcv(df, tf):
        if df.empty: return pd.DataFrame()
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'ts_event' in df.columns: df = df.set_index('ts_event')
            elif 'timestamp' in df.columns: df = df.set_index('timestamp')
        
        price_col = 'price' if 'price' in df.columns else 'last_price'
        rule = f'{tf}min'
        o = df[price_col].resample(rule).first()
        h = df[price_col].resample(rule).max()
        l = df[price_col].resample(rule).min()
        c = df[price_col].resample(rule).last()
        v = df[price_col].resample(rule).count()
        res = pd.DataFrame({'open': o, 'high': h, 'low': l, 'close': c, 'volume': v})
        return res.dropna()

    def add_indicators(df):
        # EMA
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        # ATR
        hl = df['high'] - df['low']
        hc = (df['high'] - df['close'].shift()).abs()
        lc = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df['atr_14'] = tr.rolling(14).mean()
        
        # Wick
        cr = df['high'] - df['low']
        bt = df[['open', 'close']].max(axis=1)
        bb = df[['open', 'close']].min(axis=1)
        df['wick_ratio_up'] = (df['high'] - bt) / cr
        df['wick_ratio_down'] = (bb - df['low']) / cr
        
        # --- MACRO (HONEST with SHIFT) ---
        df_1h = df.resample('1h').last()
        df_1h['ema_1h_50'] = df_1h['close'].ewm(span=50, adjust=False).mean()
        df_1h['macro_trend'] = np.where(df_1h['close'] > df_1h['ema_1h_50'], 1, -1)
        
        # SHIFT(1) is the key!
        df_1h_shifted = df_1h.shift(1)
        df['macro_trend'] = df_1h_shifted['macro_trend'].reindex(df.index, method='ffill')
        
        # Handle nan (start of data)
        df['macro_trend'] = df['macro_trend'].fillna(0)
        
        return df

    es_raw = filter_sym(raw_df, 'ES')
    nq_raw = filter_sym(raw_df, 'NQ')
    
    es_ohlcv = agg_ohlcv(es_raw, timeframe_minutes)
    nq_ohlcv = agg_ohlcv(nq_raw, timeframe_minutes)
    
    # Align
    idx = es_ohlcv.index.intersection(nq_ohlcv.index)
    es = es_ohlcv.loc[idx]
    nq = nq_ohlcv.loc[idx]
    
    es = add_indicators(es)
    nq = add_indicators(nq)
    
    return es, nq

# --- WORKER FUNCTION ---
@app.function(
    image=image, 
    volumes={REMOTE_DATA_DIR: volume}, 
    timeout=3600, 
    cpu=1.0,
    concurrency_limit=100 # POWER UP!
)
def run_backtest_chunk(configs):
    sys.path.append("/root/app")
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
    
    # Load Data (Memoized per container)
    if not hasattr(run_backtest_chunk, "data_cache"):
        if not os.path.exists(REMOTE_DBN_PATH):
            raise FileNotFoundError(f"Data file missing: {REMOTE_DBN_PATH}")
            
        tf = configs[0]['timeframe_minutes']
        # Use our INLINED honest loader
        es, nq = honest_loader(REMOTE_DBN_PATH, timeframe_minutes=tf)
        run_backtest_chunk.data_cache = (tf, es, nq)
    
    cached_tf, es_data, nq_data = run_backtest_chunk.data_cache
    
    # Reload if Tf mismatch
    target_tf = configs[0]['timeframe_minutes']
    if cached_tf != target_tf:
        es_data, nq_data = honest_loader(REMOTE_DBN_PATH, timeframe_minutes=target_tf)
        run_backtest_chunk.data_cache = (target_tf, es_data, nq_data)
        
    results = []
    
    for cfg_dict in configs:
        bt_config = BacktestConfig(**cfg_dict)
        engine = GoldenProtocolBacktest(bt_config)
        res = engine.run(es_data, nq_data)
        
        for asset in ["ES", "NQ"]:
            for direction in [TradeDirection.LONG, TradeDirection.SHORT]:
                dir_str = "LONG" if direction == TradeDirection.LONG else "SHORT"
                
                trades = [t for t in res.trades if t.asset == asset and t.sweep_direction == direction]
                if not trades: continue
                    
                wins = sum(1 for t in trades if t.state == TradeState.WIN)
                total = len(trades)
                pnl = sum(t.pnl for t in trades)
                wr = (wins / total * 100)
                
                # Loose filter to catch all potential candidates
                if total < 5: continue 
                
                results.append({
                    "config": cfg_dict,
                    "asset": asset,
                    "direction": dir_str,
                    "wr": wr,
                    "trades": total,
                    "pnl": pnl
                })
    return results

# --- ENTRYPOINT ---
@app.local_entrypoint()
def main():
    print("🚀 Generating Honest Optimization Configs (MASSIVE SCALE - 100 CPUs)...")
    
    # MASSIVE GRID SEARCH
    timeframes = [2, 5]
    fibs = [0.382, 0.5, 0.618]
    fib_stops = [0.85, 1.0, 1.15] # Varying stop distance
    expiries = [5, 10, 15, 20] 
    wicks = [0.0, 0.1, 0.25, 0.5]
    atrs = [0.0, 4.0, 6.0, 8.0]
    macros = [True, False] 
    trailing_fib = [True]
    
    configs = []
    for tf, fib, stop, exp, wick, atr, mac in itertools.product(timeframes, fibs, fib_stops, expiries, wicks, atrs, macros):
        cfg = {
            "timeframe_minutes": tf,
            "fib_entry": fib,
            "fib_stop": stop,
            "fib_target": 0.0,
            "entry_expiry_candles": exp,
            "min_wick_ratio": wick,
            "max_atr": atr,
            "use_macro_filter": mac,
            "use_trailing_fib": True,
            "entry_mode": "FIB"
        }
        configs.append(cfg)
        
    print(f"Total Configs: {len(configs)}")
    
    # Chunking - Smaller chunks for higher parallelism
    CHUNK_SIZE = 20 
    chunks = [configs[i:i + CHUNK_SIZE] for i in range(0, len(configs), CHUNK_SIZE)]
    print(f"Split into {len(chunks)} chunks for parallel execution.")
    
    output_file = "optimization_honest_results.csv"
    if os.path.exists(output_file): os.remove(output_file)
    
    print("Dispatching to Modal (Honest Run)...")
    
    total_saved = 0
    try:
        for i, results in enumerate(run_backtest_chunk.map(chunks)):
            if not results: continue
            df = pd.DataFrame(results)
            header = not os.path.exists(output_file)
            df.to_csv(output_file, mode='a', header=header, index=False)
            total_saved += len(results)
            if i % 10 == 0:
                print(f"[{i+1}/{len(chunks)}] Saved {len(results)} results.")
    except Exception as e:
        print(f"Error: {e}")
        
    print(f"Optimization Complete. Results in {output_file}")
    
    # Analysis
    if os.path.exists(output_file):
        df = pd.read_csv(output_file)
        if not df.empty:
            print("\n🏆 TOP 10 CONFIGURATIONS (By PnL):")
            print(df.sort_values("pnl", ascending=False).head(10)[["asset", "direction", "wr", "trades", "pnl", "config"]])
            
            print("\n🎯 TOP 10 CONFIGURATIONS (By Win Rate > 20 trades):")
            high_vol = df[df["trades"] >= 20]
            if not high_vol.empty:
                print(high_vol.sort_values("wr", ascending=False).head(10)[["asset", "direction", "wr", "trades", "pnl", "config"]])
        else:
            print("No valid results found.")
