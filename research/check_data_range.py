"""Full date range ES comparison with extended data"""
import modal
from modal import App, Image, Volume
import sys

APP_NAME = "es-full-range"
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
def check_data_range():
    sys.path.append("/root/app")
    from data_loader import load_and_prepare_data
    import pandas as pd
    
    output = []
    
    def log(msg):
        print(msg)
        output.append(str(msg))
    
    # Check the actual data range available
    log("="*80)
    log("CHECKING DATA RANGE IN DATABENTO FILE")
    log("="*80)
    
    es_5m, nq_5m = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=5)
    log(f"ES 5m: {es_5m.index.min()} to {es_5m.index.max()}")
    log(f"Total ES 5m candles: {len(es_5m)}")
    
    es_2m, nq_2m = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=2)
    log(f"ES 2m: {es_2m.index.min()} to {es_2m.index.max()}")
    log(f"Total ES 2m candles: {len(es_2m)}")
    
    # Check if Dec 15 and Dec 18 data exists
    log("\n" + "="*80)
    log("CHECKING IF DEC 15-23 DATA EXISTS")
    log("="*80)
    
    dec_15 = es_2m['2025-12-15':'2025-12-15']
    dec_18 = es_2m['2025-12-18':'2025-12-18']
    dec_20 = es_2m['2025-12-20':'2025-12-20']
    dec_23 = es_2m['2025-12-23':'2025-12-23']
    
    log(f"Dec 15 candles: {len(dec_15)}")
    log(f"Dec 18 candles: {len(dec_18)}")
    log(f"Dec 20 candles: {len(dec_20)}")
    log(f"Dec 23 candles: {len(dec_23)}")
    
    # Show last few candles
    log("\n--- Last 10 candles in dataset ---")
    for idx in es_2m.tail(10).index:
        log(str(idx))
    
    return output

@app.local_entrypoint()
def main():
    output = check_data_range.remote()
    
    with open("research/data_range_check.txt", "w") as f:
        f.write("\n".join(output))
    
    for line in output:
        print(line)
