from modal import App, Image, Volume
import sys
import os

APP_NAME = "verify-bot-cloud-v3"
VOLUME_NAME = "trading-data-vol"
REMOTE_DATA_DIR = "/root/data"
# Using the previously uploaded file
REMOTE_DBN_PATH = f"{REMOTE_DATA_DIR}/trades_es_nq_2025-09-21_2025-12-20.dbn"

# Define Image
image = (
    Image.debian_slim()
    # Install dependencies for bot + data loading
    .pip_install("pandas", "numpy", "databento", "alpaca-py", "python-dotenv")
    .add_local_file("alpaca_paper_trader.py", remote_path="/root/app/alpaca_paper_trader.py")
    .add_local_file("data_loader.py", remote_path="/root/app/data_loader.py")
)

app = App(APP_NAME)
volume = Volume.from_name(VOLUME_NAME, create_if_missing=True)

# Helper to run the bot logic inside cloud
@app.function(
    image=image, 
    volumes={REMOTE_DATA_DIR: volume}, 
    timeout=3600, # 1 hour
    cpu=4.0, 
    memory=16384, # 16GB RAM for Data Loading
)
def run_cloud_verification():
    import sys
    sys.path.append("/root/app")
    import pandas as pd
    import numpy as np
    import logging
    # Import Bot Logic
    from alpaca_paper_trader import BarAggregator, StrategyInstance, CONFIGS, Candle
    # Import Data Loader (reusing existing one)
    from data_loader import load_and_prepare_data
    
    # Setup Logging
    logger = logging.getLogger("CLOUD_VERIFY")
    logging.basicConfig(level=logging.INFO)
    
    print("🚀 Starting 90-Day Bot Logic Verification on Cloud...")
    
    # 1. Load Data
    print(f"Loading data from {REMOTE_DBN_PATH}...")
    # Using 1m timeframe for base resolution
    es_df, nq_df = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=1)
    print(f"Data Loaded. ES: {len(es_df)}, NQ: {len(nq_df)}")
    
    # 2. Init Bot Components
    # Filter for V8 configs
    v8_configs = [c for c in CONFIGS if "V8" in c.name]
    strats = [StrategyInstance(c) for c in v8_configs]
    
    print(f"Testing Strategies: {[s.cfg.name for s in strats]}")
    
    # Aggregators
    agg_es_2m = BarAggregator(2)
    agg_nq_2m = BarAggregator(2)
    agg_es_5m = BarAggregator(5)
    agg_nq_5m = BarAggregator(5)
    
    trades = []
    
    # 3. Simulate
    all_times = sorted(list(set(es_df.index).union(set(nq_df.index))))
    print(f"Simulating {len(all_times)} minutes...")
    
    for ts in all_times:
        c_es = None
        c_nq = None
        macro_val = 0
        
        # ES Data
        if ts in es_df.index:
            row = es_df.loc[ts]
             # Handle possible dupe rows
            if isinstance(row, pd.DataFrame): row = row.iloc[-1]
            
            # Extract Macro (Honest Shift 1 is built into data_loader)
            macro_val = int(row['macro_trend'])
            c_es = Candle(ts, float(row['open']), float(row['high']), float(row['low']), float(row['close']), float(row['volume']), "SPY")
            
        # NQ Data
        if ts in nq_df.index:
            row = nq_df.loc[ts]
            if isinstance(row, pd.DataFrame): row = row.iloc[-1]
            c_nq = Candle(ts, float(row['open']), float(row['high']), float(row['low']), float(row['close']), float(row['volume']), "QQQ")
            
        # Update Aggs
        es_2m_bar = agg_es_2m.add_bar("SPY", c_es) if c_es else None
        nq_2m_bar = agg_nq_2m.add_bar("QQQ", c_nq) if c_nq else None
        es_5m_bar = agg_es_5m.add_bar("SPY", c_es) if c_es else None
        nq_5m_bar = agg_nq_5m.add_bar("QQQ", c_nq) if c_nq else None
        
        # Check Strats
        for strat in strats:
            tf = strat.cfg.timeframe
            target = None
            ref = None
            
            if tf == 2 and es_2m_bar and nq_2m_bar and es_2m_bar.timestamp == nq_2m_bar.timestamp:
                target = es_2m_bar if strat.cfg.target_symbol == "SPY" else nq_2m_bar
                ref = nq_2m_bar if strat.cfg.target_symbol == "SPY" else es_2m_bar
            elif tf == 5 and es_5m_bar and nq_5m_bar and es_5m_bar.timestamp == nq_5m_bar.timestamp:
                target = es_5m_bar if strat.cfg.target_symbol == "SPY" else nq_5m_bar
                ref = nq_5m_bar if strat.cfg.target_symbol == "SPY" else es_5m_bar
                
            if target and ref:
                sig = strat.on_candles(target, ref, macro_val)
                if sig:
                    trades.append({
                        'ts': ts,
                        'strat': strat.cfg.name,
                        'entry': sig['entry'],
                        'stop': sig['stop'],
                        'target': sig['target'],
                        'side': sig['side']
                    })
    
    print(f"Simulation Complete. Total Signals: {len(trades)}")
    
    # 4. Verify Outcomes (Simple Forward Search)
    wins = 0
    losses = 0
    total_pnl = 0.0
    
    for t in trades:
        entry = t['entry']
        stop = t['stop']
        target = t['target']
        is_long = "BUY" in str(t['side'])
        start_ts = t['ts']
        
        # Determine DF
        df = es_df if "ES" in t['strat'] else nq_df
        subset = df[df.index > start_ts]
        
        filled = False
        outcome = "OPEN"
        pnl = 0.0
        
        for f_ts, row in subset.iterrows():
            if isinstance(row, pd.DataFrame): row = row.iloc[0]
            h, l = float(row['high']), float(row['low'])
            
            if not filled:
                if is_long:
                     if l <= entry: filled = True
                else:
                     if h >= entry: filled = True
            
            if filled:
                if is_long:
                    if l <= stop: outcome="LOSS"; pnl= -abs(entry-stop); break
                    if h >= target: outcome="WIN"; pnl= abs(target-entry); break # Using 0 Target? No, Wait.
                    # Wait. V8 config has target=0.0. logic calculates one.
                    # sig['target'] comes from strategy logic. It IS the calculated target.
                else:
                    if h >= stop: outcome="LOSS"; pnl= -abs(stop-entry); break
                    if l <= target: outcome="WIN"; pnl= abs(entry-target); break
        
        if outcome == "WIN": wins +=1; total_pnl += pnl
        elif outcome == "LOSS": losses +=1; total_pnl += pnl
        
    if wins+losses > 0:
        wr = (wins/(wins+losses))*100
        print(f"FINAL STATS: WR: {wr:.1f}% | PnL: {total_pnl:.2f} | Trades: {wins+losses}")
    
    return f"WR: {wr:.1f}% | PnL: {total_pnl:.2f}" if wins+losses > 0 else "No Trades"

@app.local_entrypoint()
def main():
    print(run_cloud_verification.remote())
