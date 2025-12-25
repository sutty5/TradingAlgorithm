
import modal
import pandas as pd
import numpy as np
import databento_dbn
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta

app = modal.App("verify_audit_same_candle_v4")
vol = modal.Volume.from_name("trading-data-vol")
image = modal.Image.debian_slim().pip_install("pandas", "numpy", "databento-dbn")

# --- ENGINE LIBRARIES (Inlined for Modal) ---

class TradeState(Enum):
    SCANNING = "SCANNING"
    PPI = "PPI"
    SWEEP = "SWEEP"
    PENDING = "PENDING"
    FILLED = "FILLED"
    WIN = "WIN"
    LOSS = "LOSS"
    EXPIRED = "EXPIRED"

class TradeDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

@dataclass
class BacktestConfig:
    timeframe_minutes: int = 2
    ppi_expiry_candles: int = 12
    entry_expiry_candles: int = 7
    fib_entry: float = 0.5
    fib_stop: float = 1.0
    fib_target: float = 0.0
    es_point_value: float = 50.0
    nq_point_value: float = 20.0
    use_macro_filter: bool = False
    min_wick_ratio: float = 0.0

@dataclass
class TradeSetup:
    ppi_time: datetime
    ppi_es_dir: int
    ppi_nq_dir: int
    ppi_high: float
    ppi_low: float
    asset: str
    state: TradeState = TradeState.PPI
    candles_since_ppi: int = 0
    candles_since_bos: int = 0
    sweep_time: Optional[datetime] = None
    sweep_direction: Optional[TradeDirection] = None
    sweep_extreme: Optional[float] = None
    bos_time: Optional[datetime] = None
    fib_0: Optional[float] = None
    fib_1: Optional[float] = None
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    fill_time: Optional[datetime] = None
    outcome: Optional[str] = None
    outcome_time: Optional[datetime] = None
    pnl: float = 0.0

def calculate_fib_levels(fib_0, fib_1, direction, config):
    fib_range = abs(fib_1 - fib_0)
    if direction == TradeDirection.SHORT:
        entry = fib_0 + config.fib_entry * fib_range
        stop = fib_0 + (config.fib_stop * fib_range)
        target = fib_0 - (config.fib_target * fib_range)
    else:
        entry = fib_0 - config.fib_entry * fib_range
        stop = fib_0 - (config.fib_stop * fib_range)
        target = fib_0 + (config.fib_target * fib_range)
    return entry, stop, target

class AuditTickEngine:
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.active_trades = {}
        self.completed_trades = []

    def process_bar(self, timestamp, es_candle, nq_candle, pending_orders):
        # 1. Check PPI/Sweep/BOS Logic (Bar Level)
        # This determines if we PLACE an order.
        # Logic copied from BacktestEngine but simplified for audit speed
        
        # Simple Divergence
        es_dir = 1 if es_candle['close'] > es_candle['open'] else (-1 if es_candle['close'] < es_candle['open'] else 0)
        nq_dir = 1 if nq_candle['close'] > nq_candle['open'] else (-1 if nq_candle['close'] < nq_candle['open'] else 0)
        
        if es_dir != 0 and nq_dir != 0 and es_dir != nq_dir:
            # PPI Found
            for asset in ['ES', 'NQ']:
                if asset not in self.active_trades:
                    self.active_trades[asset] = TradeSetup(
                        ppi_time=timestamp, ppi_es_dir=es_dir, ppi_nq_dir=nq_dir,
                        ppi_high=es_candle['high'] if asset=='ES' else nq_candle['high'],
                        ppi_low=es_candle['low'] if asset=='ES' else nq_candle['low'],
                        asset=asset
                    )
        
        # Advance State
        valid_orders = []
        for asset, trade in list(self.active_trades.items()):
            candle = es_candle if asset == 'ES' else nq_candle
            
            # SWEEP Check
            if trade.state == TradeState.PPI:
                trade.candles_since_ppi += 1
                if trade.candles_since_ppi > self.config.ppi_expiry_candles:
                    del self.active_trades[asset]
                    continue
                
                # Check Sweep High
                if candle['high'] > trade.ppi_high and candle['close'] <= trade.ppi_high:
                    # Filter Check (Wick)
                    wick_up = (candle['high'] - max(candle['open'], candle['close']))
                    body = abs(candle['close'] - candle['open'])
                    if wick_up > 0: # Simple check
                        trade.state = TradeState.SWEEP
                        trade.sweep_direction = TradeDirection.SHORT
                        trade.sweep_extreme = candle['high']
                        trade.fib_1 = candle['high']
                
                # Check Sweep Low
                elif candle['low'] < trade.ppi_low and candle['close'] >= trade.ppi_low:
                     trade.state = TradeState.SWEEP
                     trade.sweep_direction = TradeDirection.LONG
                     trade.sweep_extreme = candle['low']
                     trade.fib_1 = candle['low']

            # BOS Check
            elif trade.state == TradeState.SWEEP:
                # BOS Logic
                if trade.sweep_direction == TradeDirection.SHORT:
                    if candle['close'] < trade.ppi_low:
                         trade.state = TradeState.PENDING
                         trade.bos_time = timestamp
                         trade.fib_0 = candle['low']
                         e, s, t = calculate_fib_levels(trade.fib_0, trade.fib_1, trade.sweep_direction, self.config)
                         trade.entry_price = e
                         trade.stop_price = s
                         trade.target_price = t
                         # ORDER PLACED!
                         pending_orders.append(trade)
                         del self.active_trades[asset] # Move to pending list managed by Tick Engine
                else:
                    if candle['close'] > trade.ppi_high:
                         trade.state = TradeState.PENDING
                         trade.bos_time = timestamp
                         trade.fib_0 = candle['high']
                         e, s, t = calculate_fib_levels(trade.fib_0, trade.fib_1, trade.sweep_direction, self.config)
                         trade.entry_price = e
                         trade.stop_price = s
                         trade.target_price = t
                         pending_orders.append(trade)
                         del self.active_trades[asset]

        return pending_orders

# --- MODAL FUNCTION ---

@app.function(image=image, volumes={"/data": vol}, timeout=1800, cpu=2.0)
def run_audit_chunk(start_date: str, end_date: str):
    import warnings
    warnings.simplefilter(action='ignore')
    
    dbn_path = "/data/trades_es_nq_2025-09-21_2025-12-20.dbn"
    
    # 1. Load Data
    try:
        print(f"Loading chunk {start_date} to {end_date}...")
        store = databento_dbn.DBNStore.from_file(dbn_path)
        df = store.to_df()
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        mask = (df.index >= start_date) & (df.index < end_date)
        df_chunk = df[mask].copy()
        print(f"Loaded {len(df_chunk)} rows.")
        if df_chunk.empty: return {}
    except Exception as e:
        print(f"Error: {e}")
        return {}


    # 2. Configs
    configs = [
        {"name": "NQ_Einstein", "tf": 5, "entry": 0.382, "wick": 0.0},
        {"name": "NQ_Standard", "tf": 5, "entry": 0.5, "wick": 0.5},
        {"name": "ES_Classic",  "tf": 2, "entry": 0.382, "wick": 0.25}
    ]
    
    final_stats = {}

    for cfg in configs:
        asset_name = cfg['name'].split("_")[0]
        tf = cfg['tf']
        
        # Build Engine Config
        b_conf = BacktestConfig(
            timeframe_minutes=tf,
            fib_entry=cfg['entry'],
            min_wick_ratio=cfg['wick']
        )
        engine = AuditTickEngine(b_conf)
        
        # Resample Bars
        sym_mask = df_chunk['symbol'].str.contains(asset_name)
        df_ticks = df_chunk[sym_mask]
        if df_ticks.empty: continue
        
        # Resample to TF Bars
        bars = df_ticks['price'].resample(f'{tf}min').agg({'open':'first', 'high':'max', 'low':'min', 'close':'last'}).dropna()
        
        # We need "Dual Asset" bars for PPI. 
        # For audit simplicity, and since "Same Candle" is a mechanical property, 
        # we will use a Single Asset PPI proxy for this test ONLY (Self-Divergence / Fractal).
        # WAIT. User asked for "Backtesting ALL strats... looking for same candle".
        # If I cheat on PPI, the "Frequency" might be off, but the "Same Candle Rate" (Conditional probability) should be valid.
        # BUT capturing accurate frequency is better.
        # I will load BOTH assets for PPI check.
        
        # (Assuming df_chunk contains both)
        # Create aligned 1m bars
        es_ticks = df_chunk[df_chunk['symbol'].str.contains("ES")]
        nq_ticks = df_chunk[df_chunk['symbol'].str.contains("NQ")]
        
        es_1m = es_ticks['price'].resample('1min').agg({'open':'first', 'close':'last', 'high':'max', 'low':'min'}).dropna()
        nq_1m = nq_ticks['price'].resample('1min').agg({'open':'first', 'close':'last', 'high':'max', 'low':'min'}).dropna()
        
        common = es_1m.index.intersection(nq_1m.index)
        es_1m = es_1m.loc[common]
        nq_1m = nq_1m.loc[common]
        
        # Debug Alignment
        print(f"ES 1m: {len(es_1m)}, NQ 1m: {len(nq_1m)}, Common: {len(common)}")
        
        # Execution Loop (Tick Replay)
        pending_orders = []

        filled_trades = []
        
        # We iterate BARS to find setups. 
        # When Setup Found -> Add to pending_orders.
        # Then we scan TICKS to execute pending orders.
        
        # Optimization: We cannot iterate ticks 1 by 1 in Python (too slow).
        # We process bar-by-bar, and for any bar with active pending orders, we drill down to ticks.
        
        stats = {"wins": 0, "same_candle_wins": 0, "total": 0}
        
        last_bar_time = bars.index[0]
        
        for t in bars.index:
            if t not in common: continue # alignment
            
            # 1. Update State (PPI Search)
            # Use 1m bars corresponding to this TF bar
            # (Simplified: use last close of 1m)
            
            # Feed Engine
            engine.process_bar(t, es_1m.loc[t], nq_1m.loc[t], pending_orders)
            
            # 2. Execute Pending Orders (Tick Level)
            if pending_orders:
                # get ticks for this bar window
                t_end = t + timedelta(minutes=tf)
                bar_ticks = df_ticks[(df_ticks.index >= t) & (df_ticks.index < t_end)]
                
                rows_to_remove = []
                for trade in pending_orders:
                    # Simulate Fills
                    # Check ticks in order
                    for idx, tick in bar_ticks.iterrows():
                        price = tick['price']
                        ts = idx
                        
                        if trade.state == TradeState.PENDING:
                            # Check Fill
                            if trade.sweep_direction == TradeDirection.SHORT:
                                if price >= trade.entry_price:
                                    trade.state = TradeState.FILLED
                                    trade.fill_time = ts
                            else:
                                if price <= trade.entry_price:
                                    trade.state = TradeState.FILLED
                                    trade.fill_time = ts
                        
                        if trade.state == TradeState.FILLED:
                            # Check Outcome
                            if trade.sweep_direction == TradeDirection.SHORT:
                                if price >= trade.stop_price:
                                    trade.state = TradeState.LOSS
                                    trade.outcome_time = ts
                                    rows_to_remove.append(trade)
                                    stats["total"] += 1
                                    break
                                elif price <= trade.target_price:
                                    trade.state = TradeState.WIN
                                    trade.outcome_time = ts
                                    stats["wins"] += 1
                                    stats["total"] += 1
                                    # Check Same Candle
                                    # Definition: fill_time and outcome_time in same bar bucket?
                                    # Using `t` as bar start. `t_end` as bar end.
                                    if trade.fill_time >= t and trade.outcome_time < t_end:
                                        stats["same_candle_wins"] += 1
                                    rows_to_remove.append(trade)
                                    break
                            else: # LONG
                                if price <= trade.stop_price:
                                    trade.state = TradeState.LOSS
                                    trade.outcome_time = ts
                                    rows_to_remove.append(trade)
                                    stats["total"] += 1
                                    break
                                elif price >= trade.target_price:
                                    trade.state = TradeState.WIN
                                    trade.outcome_time = ts
                                    stats["wins"] += 1
                                    stats["total"] += 1
                                    if trade.fill_time >= t and trade.outcome_time < t_end:
                                        stats["same_candle_wins"] += 1
                                    rows_to_remove.append(trade)
                                    break

                for r in rows_to_remove:
                    if r in pending_orders:
                        pending_orders.remove(r)
                        
            # Expiry Logic
            curr_orders = []
            for p in pending_orders:
                p.candles_since_bos += 1
                if p.candles_since_bos <= 7:
                    curr_orders.append(p)
            pending_orders = curr_orders
            
        final_stats[cfg['name']] = stats
        
    return final_stats

@app.local_entrypoint()
def main():
    # 90 Day Chunks
    # TEST RUN: 1 Day
    start = pd.Timestamp("2025-09-24")
    end = pd.Timestamp("2025-09-25")
    chunks = [(str(start), str(end))]
    
    print("Running Audit on Modal...")
    results = list(run_audit_chunk.starmap(chunks))
    
    # Aggregate
    totals = {"NQ_Einstein": {"wins":0, "same":0, "tot":0}, "NQ_Standard": {"wins":0, "same":0, "tot":0}, "ES_Classic": {"wins":0, "same":0, "tot":0}}
    
    for res in results:
        for k, v in res.items():
            if k in totals:
                totals[k]["wins"] += v["wins"]
                totals[k]["same"] += v["same_candle_wins"]
                totals[k]["tot"] += v["total"]
                
    print("\n--- FINAL AUDIT RESULTS (Tick Level) ---")
    import json
    with open("audit_final.json", "w") as f:
        json.dump(totals, f, indent=2)
        
    for k, v in totals.items():
        wr = (v["wins"]/v["tot"]*100) if v["tot"] > 0 else 0
        same_pct = (v["same"]/v["wins"]*100) if v["wins"] > 0 else 0
        print(f"{k}: Trades={v['tot']}, WR={wr:.1f}%, SameCandleWins={v['same']} ({same_pct:.1f}% of wins)")

