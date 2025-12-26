import databento as db
import sys

DATA_PATH = r"c:\Users\sutty\TradingStrategyDev\data\databento_trades\trades_es_nq_2025-09-21_2025-12-20.dbn"

try:
    stored = db.DBNStore.from_file(DATA_PATH)
    print("MAPPINGS:")
    print(stored.mappings)
    print("\nSYMBOLOGY:")
    print(stored.symbology)
except Exception as e:
    print(f"Error: {e}")
