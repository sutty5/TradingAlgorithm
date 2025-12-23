
import pandas as pd
from datetime import timedelta

def analyze_confluence():
    print("Testing 'Twin Dragon' Hypothesis (Confluence)...")
    try:
        df = pd.read_csv('diagnostic_results.csv')
    except FileNotFoundError:
        print("diagnostic_results.csv not found.")
        return
        
    # We need timestamps. diagnostics might have them?
    # Wait, my diagnostic script saved 'hour' but maybe not full timestamp?
    # Let's check the CSV structure.
    print("Columns:", df.columns.tolist())
    
    # Ah, I didn't save the full timestamp in diagnostic_analysis.py. 
    # I only saved 'hour'. 
    # I need to re-run a lightweight scan to get timestamps.
    
    print("Timestamp missing. Re-fetching trade logs...")
    
    # We can use the cached data and run a quick scan using backtest_engine
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig
    from data_loader import load_and_prepare_data
    
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    es_data, nq_data = load_and_prepare_data(dbn_path, timeframe_minutes=2)
    
    # Loose config to get all setups
    config = BacktestConfig(
        timeframe_minutes=2,
        fib_entry=0.618,
        use_trend_filter=False
    )
    
    engine = GoldenProtocolBacktest(config)
    results = engine.run(es_data, nq_data)
    
    # Extract trades with timestamps
    trades = []
    for t in results.trades:
        # filter for valid setups (SWEEP or later)
        if not t.sweep_time: continue
        trades.append({
            'asset': t.asset,
            'time': t.sweep_time, # Confirmation time
            'dir': t.sweep_direction.name,
            'state': t.state.name,
            'pnl': t.pnl
        })
        
    df_trades = pd.DataFrame(trades)
    print(f"Found {len(df_trades)} potential setups.")
    
    # Confluence Check
    # For every ES trade, look for NQ trade within X minutes
    results = []
    
    window = pd.Timedelta(minutes=5)
    
    # Separate
    es_trades = df_trades[df_trades['asset'] == 'ES'].copy()
    nq_trades = df_trades[df_trades['asset'] == 'NQ'].copy()
    
    print(f"ES Trades: {len(es_trades)}")
    print(f"NQ Trades: {len(nq_trades)}")
    
    confluence_trades = []
    
    # Iterate ES (can be optimized but loop is fine for <2000 items)
    for idx, es_t in es_trades.iterrows():
        # Match time AND direction
        matches = nq_trades[
            (nq_trades['dir'] == es_t['dir']) & 
            (nq_trades['time'] >= es_t['time'] - window) &
            (nq_trades['time'] <= es_t['time'] + window)
        ]
        
        if not matches.empty:
            # Confluence found!
            # Outcome? If either wins? Or both must win?
            # Strategy: We enter BOTH? Or just NQ? 
            # Let's assume we enter NQ if confluent (since NQ pays better usually)
            
            # Add to list
            nq_match = matches.iloc[0] # Take first match
            confluence_trades.append(nq_match)
            
    # Calculate stats
    if not confluence_trades:
        print("No confluence found.")
        return
        
    cf_df = pd.DataFrame(confluence_trades)
    # Deduplicate (if multiple ES matched same NQ)
    cf_df = cf_df.drop_duplicates(subset=['time'])
    
    wins = len(cf_df[cf_df['state'] == 'WIN'])
    losses = len(cf_df[cf_df['state'] == 'LOSS'])
    total = wins + losses # Ignore pending/expired for WR calc if not filled? 
    # Actually backtest engine marks filled outcomes.
    
    print("\n--- CONFLUENCE RESULTS (Twin Dragon) ---")
    print(f"Time Window: +/- {window.seconds//60} mins")
    print(f"Total Signals: {len(cf_df)}")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    
    if total > 0:
        print(f"Win Rate: {wins/total*100:.2f}%")
        print(f"Total PnL: ${cf_df['pnl'].sum():,.2f}")
    else:
        print("No filled trades.")

if __name__ == "__main__":
    analyze_confluence()
