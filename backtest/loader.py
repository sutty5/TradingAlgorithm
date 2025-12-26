import databento as db
from datetime import datetime
from typing import Generator, Tuple, Dict

def load_trades(file_path: str) -> Generator[Tuple[int, str, float, int], None, None]:
    try:
        print(f"Loading data from {file_path}...")
        stored = db.DBNStore.from_file(file_path)
        
        # Build ID Map
        id_map = {}
        
        # Debug Mappings
        # print("Mappings keys:", list(stored.mappings.keys()))
        
        # Structure: { "NQ.c.0": [ { 'symbol': '158704', ... } ] }
        # Key is the Query Symbol (e.g. "ES.c.0"), Value is list of intervals where 'symbol' is the Instrument ID.
        
        for query_sym, intervals in stored.mappings.items():
            target_sym = None
            if "ES" in query_sym:
                target_sym = "ES"
            elif "NQ" in query_sym:
                target_sym = "NQ"
            
            if target_sym:
                for interval in intervals:
                    # interval['symbol'] holds the numeric Instrument ID as a string
                    i_id_str = interval.get('symbol')
                    if i_id_str:
                        try:
                            id_map[int(i_id_str)] = target_sym
                        except ValueError:
                            pass # handle if it's not an int

        
        print(f"Instrument Map: {id_map}")
        
        if not id_map:
            print("Warning: Map empty. Trying to guess IDs from first few records...")
        
        count = 0
        for trade in stored:
            # Check for instrument_id
            # Python bindings often expose it directly as 'instrument_id' or 'publisher_id'
            # 'hd' might be a property that returns a header object, but if error, maybe pure field.
            
            try:
                # Try direct access first (common in recent ctypes bindings)
                if hasattr(trade, 'instrument_id'):
                    i_id = trade.instrument_id
                elif hasattr(trade, 'hd'):
                    i_id = trade.hd.instrument_id
                else:
                    # Fallback: maybe it's accessible via dictionary-like? 
                    # But it's usually an object.
                    # Print dir once? 
                    # Let's Skip if we can't find ID.
                    continue
            except:
                continue
            
            if i_id not in id_map:
                continue
                
            sym = id_map[i_id]
            
            # Price
            # Usually trade.price is int64 (fixed precision 1e-9)
            # But checking type: if float, use it.
            p = trade.price
            if isinstance(p, int):
                price = p * 1e-9
            else:
                price = float(p)
                
            size = trade.size
            ts = trade.ts_event
            
            yield (ts, sym, price, size)
            
            count += 1
            if count % 1_000_000 == 0:
                print(f"Processed {count/1_000_000:.1f}M trades... (Last: {sym} @ {price:.2f})", end='\r')

    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    # Test stub
    pass
