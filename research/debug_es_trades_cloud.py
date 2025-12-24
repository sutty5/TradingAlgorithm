"""Debug: Check what happens at specific TradingView trade timestamps"""
import modal
from modal import App, Image, Volume
import sys

APP_NAME = "debug-es-trades"
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
def debug_trades():
    sys.path.append("/root/app")
    from data_loader import load_and_prepare_data
    import pandas as pd
    
    output = []
    
    def log(msg):
        print(msg)
        output.append(str(msg))
    
    # TradingView ES 5m LONG trades (from the Excel)
    tv_es5m_trades = [
        "2025-11-28 13:40:00",  # Trade 1 - Entry
        "2025-12-01 19:00:00",  # Trade 2 - Entry
        "2025-12-03 15:10:00",  # Trade 3 - Entry
        "2025-12-05 08:25:00",  # Trade 4 - Entry
        "2025-12-05 17:00:00",  # Trade 5 - Entry
        "2025-12-07 23:05:00",  # Trade 6 - Entry
        "2025-12-11 14:45:00",  # Trade 7 - Entry
        "2025-12-11 18:25:00",  # Trade 8 - Entry
    ]
    
    # TradingView ES 2m SHORT trades
    tv_es2m_trades = [
        "2025-12-15 16:48:00",  # Trade 1 - Entry
        "2025-12-18 13:08:00",  # Trade 2 - Entry
    ]
    
    # Python ES 2m SHORT trades (from comparison output - first few)
    py_es2m_trades = [
        "2025-12-01 02:16:00",
        "2025-12-01 02:36:00", 
        "2025-12-01 04:22:00",
        "2025-12-08 15:54:00",
    ]
    
    # Load 5m data for ES LONG analysis
    log("\n" + "="*80)
    log("ES 5m DATA ANALYSIS")
    log("="*80)
    
    es_5m, nq_5m = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=5)
    
    for ts_str in tv_es5m_trades[:4]:  # First 4 trades
        ts = pd.Timestamp(ts_str, tz='UTC')
        log(f"\n--- TradingView Trade Entry: {ts_str} ---")
        
        # Get the candle and surrounding context
        start_ts = ts - pd.Timedelta(minutes=60)  # 12 x 5m = 60 min lookback for PPI
        end_ts = ts + pd.Timedelta(minutes=5)
        
        es_window = es_5m[(es_5m.index >= start_ts) & (es_5m.index <= end_ts)]
        nq_window = nq_5m[(nq_5m.index >= start_ts) & (nq_5m.index <= end_ts)]
        
        for idx in es_window.index:
            if idx in nq_window.index:
                es_row = es_window.loc[idx]
                nq_row = nq_window.loc[idx]
                
                es_dir = "GREEN" if es_row['close'] > es_row['open'] else "RED"
                nq_dir = "GREEN" if nq_row['close'] > nq_row['open'] else "RED"
                is_div = es_dir != nq_dir
                
                # Check macro trend
                macro = es_row.get('macro_trend', 'N/A')
                
                # Wick ratio
                wick = es_row.get('wick_ratio_down', 0)
                
                marker = "***" if idx == ts else "   "
                log(f"{marker} {idx} | ES:{es_dir} NQ:{nq_dir} | DIV:{is_div} | Macro:{macro} | Wick:{wick:.2f}")
    
    # Load 2m data for ES SHORT analysis
    log("\n" + "="*80)
    log("ES 2m DATA ANALYSIS - Why TradingView only found 2 trades?")
    log("="*80)
    
    es_2m, nq_2m = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=2)
    
    # Check a sample of Python trades that TradingView missed
    log("\n--- Checking Python trades that TradingView MISSED ---")
    for ts_str in py_es2m_trades:
        ts = pd.Timestamp(ts_str, tz='UTC')
        log(f"\n--- Python Trade (TV missed): {ts_str} ---")
        
        start_ts = ts - pd.Timedelta(minutes=30)  # 15 x 2m = 30 min lookback
        end_ts = ts + pd.Timedelta(minutes=4)
        
        es_window = es_2m[(es_2m.index >= start_ts) & (es_2m.index <= end_ts)]
        nq_window = nq_2m[(nq_2m.index >= start_ts) & (nq_2m.index <= end_ts)]
        
        for idx in es_window.index:
            if idx in nq_window.index:
                es_row = es_window.loc[idx]
                nq_row = nq_window.loc[idx]
                
                es_dir = "GREEN" if es_row['close'] > es_row['open'] else "RED"
                nq_dir = "GREEN" if nq_row['close'] > nq_row['open'] else "RED"
                is_div = es_dir != nq_dir
                
                macro = es_row.get('macro_trend', 'N/A')
                wick_up = es_row.get('wick_ratio_up', 0)
                atr = es_row.get('atr_14', 0)
                
                # Check sweep conditions
                can_be_bear_sweep = "POSSIBLE" if is_div else "NO_DIV"
                
                marker = "***" if idx == ts else "   "
                log(f"{marker} {idx} | ES:{es_dir} NQ:{nq_dir} | DIV:{is_div} | Macro:{macro} | WickUp:{wick_up:.2f} | ATR:{atr:.2f}")
    
    # Check the TradingView 2m trades
    log("\n--- Checking TradingView 2m trades (what TradingView DID find) ---")
    for ts_str in tv_es2m_trades:
        ts = pd.Timestamp(ts_str, tz='UTC')
        log(f"\n--- TradingView Trade (Dec): {ts_str} ---")
        
        start_ts = ts - pd.Timedelta(minutes=30)
        end_ts = ts + pd.Timedelta(minutes=4)
        
        es_window = es_2m[(es_2m.index >= start_ts) & (es_2m.index <= end_ts)]
        nq_window = nq_2m[(nq_2m.index >= start_ts) & (nq_2m.index <= end_ts)]
        
        for idx in es_window.index:
            if idx in nq_window.index:
                es_row = es_window.loc[idx]
                nq_row = nq_window.loc[idx]
                
                es_dir = "GREEN" if es_row['close'] > es_row['open'] else "RED"
                nq_dir = "GREEN" if nq_row['close'] > nq_row['open'] else "RED"
                is_div = es_dir != nq_dir
                
                macro = es_row.get('macro_trend', 'N/A')
                wick_up = es_row.get('wick_ratio_up', 0)
                atr = es_row.get('atr_14', 0)
                
                marker = "***" if idx == ts else "   "
                log(f"{marker} {idx} | ES:{es_dir} NQ:{nq_dir} | DIV:{is_div} | Macro:{macro} | WickUp:{wick_up:.2f} | ATR:{atr:.2f}")
    
    return output

@app.local_entrypoint()
def main():
    output = debug_trades.remote()
    
    with open("research/debug_es_trades.txt", "w") as f:
        f.write("\n".join(output))
    
    print("Debug output saved to research/debug_es_trades.txt")
    print("\nSample output:")
    for line in output[:30]:
        print(line)
