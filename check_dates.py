
import pandas as pd
from data_loader import load_dbn_file

def check_dates():
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    print(f"Checking date range in {dbn_path}...")
    
    # We can load the parquet cache if it exists for speed, or just load raw small chunk
    # Let's try to infer from filename first (it says Sep 21 - Dec 20)
    # So 3 weeks back from Dec 20 is approx Dec 1.
    
    # I'll create a script to verify exact timestamps in the cache
    from pathlib import Path
    cache_dir = Path("data/cache")
    files = list(cache_dir.glob("*_nq_2m.parquet"))
    
    if files:
        df = pd.read_parquet(files[0])
        print(f"Data Loaded from Cache.")
        print(f"Start: {df.index.min()}")
        print(f"End: {df.index.max()}")
        
        # Calculate split date
        end_date = df.index.max()
        start_sprint = end_date - pd.Timedelta(weeks=3)
        print(f"3-Week Sprint Start: {start_sprint}")
    else:
        print("No cache found. Using manual dates.")

if __name__ == "__main__":
    check_dates()
