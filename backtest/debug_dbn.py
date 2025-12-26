import databento as db
import sys

DATA_PATH = r"c:\Users\sutty\TradingStrategyDev\data\databento_trades\trades_es_nq_2025-09-21_2025-12-20.dbn"

try:
    print(f"Opening {DATA_PATH}...")
    stored = db.DBNStore.from_file(DATA_PATH)
    print("Metadata:")
    print(stored.mappings)
    print(stored.symbology)
    
    print("\nFirst 3 records:")
    for i, trade in enumerate(stored):
        if i >= 3: break
        print(f"Record {i}: {type(trade)}")
        print(dir(trade))
        try:
            print(f"Fields: {trade}")
        except:
            pass
except Exception as e:
    print(f"Error: {e}")
