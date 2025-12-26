import databento as db
import sys

DATA_PATH = r"c:\Users\sutty\TradingStrategyDev\data\databento_trades\trades_es_nq_2025-09-21_2025-12-20.dbn"

try:
    print(f"Opening {DATA_PATH}...")
    stored = db.DBNStore.from_file(DATA_PATH)
    print("\n--- MAPPPINGS ---")
    mappings = stored.mappings
    print(f"Type: {type(mappings)}")
    print(mappings)
    
    print("\n--- SYMBOLOGY ---")
    symbology = stored.symbology
    print(f"Type: {type(symbology)}")
    print(symbology)
    
    # Try to find one ID
    for i, trade in enumerate(stored):
        if i > 0: break
        print(f"\nSample Trade Header: {trade.hd}")
        print(f"Instrument ID: {trade.hd.instrument_id}")
        
except Exception as e:
    print(f"Error: {e}")
