"""Check data columns"""
import modal
from modal import App, Image, Volume
import sys

APP_NAME = "check-cols"
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
def check_cols():
    sys.path.append("/root/app")
    from data_loader import load_and_prepare_data
    
    es_data, nq_data = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=5)
    
    print("ES Columns:", list(es_data.columns))
    print()
    print("NQ Columns:", list(nq_data.columns))
    
    has_wick = 'wick_ratio_down' in es_data.columns
    print(f"\nHas wick_ratio_down column: {has_wick}")
    
    return list(es_data.columns)

@app.local_entrypoint()
def main():
    cols = check_cols.remote()
    print(f"Columns: {cols}")
    with open("data_columns.txt", "w") as f:
        f.write(str(cols))
