"""Simple debug - count divergences in November/December"""
import modal
from modal import App, Image, Volume
import sys

APP_NAME = "count-divergences"
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
def count_divergences():
    sys.path.append("/root/app")
    from data_loader import load_and_prepare_data
    import pandas as pd
    
    print("Loading 5m data...")
    es_data, nq_data = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=5)
    
    # Filter to Nov 28 - Dec 20
    es_data = es_data['2025-11-28':'2025-12-20']
    nq_data = nq_data['2025-11-28':'2025-12-20']
    
    print(f"Date range: {es_data.index.min()} to {es_data.index.max()}")
    print(f"ES candles: {len(es_data)}, NQ candles: {len(nq_data)}")
    
    divergences = 0
    for idx in es_data.index:
        if idx in nq_data.index:
            es_row = es_data.loc[idx]
            nq_row = nq_data.loc[idx]
            
            es_dir = 1 if es_row['close'] > es_row['open'] else -1
            nq_dir = 1 if nq_row['close'] > nq_row['open'] else -1
            
            es_body = abs(es_row['close'] - es_row['open'])
            nq_body = abs(nq_row['close'] - nq_row['open'])
            
            # Doji check
            es_doji = es_body <= 0.5
            nq_doji = nq_body <= 1.0
            
            if es_dir != nq_dir and not es_doji and not nq_doji:
                divergences += 1
    
    print(f"\n*** DIVERGENCES (PPIs) FOUND: {divergences} ***")
    return divergences

@app.local_entrypoint()
def main():
    count = count_divergences.remote()
    print(f"Total divergences: {count}")
    with open("divergence_count.txt", "w") as f:
        f.write(f"Total divergences in Nov 28 - Dec 20: {count}")
