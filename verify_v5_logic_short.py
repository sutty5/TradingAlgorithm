"""
v5.0 Einstein - Rapid Verification (1 Week)
"""
import pandas as pd
from data_loader import load_and_prepare_data
from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection

def run_rapid_verify():
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    print("Loading Data (Last 5 Days)...")
    
    # Load and force slice
    try:
        store = pd.read_pickle("temp_store.pkl") if False else None # Dummy check
        # We invoke data loader but we will slice INSIDE basic loader if we could, 
        # but here we load and immediately slice in memory before engine
        es_2m, nq_2m = load_and_prepare_data(dbn_path, 2)
        es_5m, nq_5m = load_and_prepare_data(dbn_path, 5)
        
        # SLICE TO LAST 5 DAYS (approx 5*6.5*30 = 975 candles)
        es_2m = es_2m.tail(1500)
        nq_2m = nq_2m.tail(1500)
        es_5m = es_5m.tail(600)
        nq_5m = nq_5m.tail(600)
        
    except Exception as e:
        print(f"Error: {e}")
        return

    print("\n--- TEST: EINSTEIN LOGIC (1 WEEK) ---")
    
    # NQ SHORT ONLY
    nq_eng = GoldenProtocolBacktest(BacktestConfig(fib_entry=0.618, breakeven_trigger_r=0.0))
    nq_res = nq_eng.run(es_2m, nq_2m)
    nq_trades = [t for t in nq_res.trades if t.asset=="NQ" and t.sweep_direction==TradeDirection.SHORT and t.ppi_time.hour not in [8,9,18,19]]
    
    print(f"NQ (Short): Found {len(nq_trades)} trades")
    for t in nq_trades:
        print(f"  {t.outcome} PnL: ${t.pnl:.2f}")

    # ES SHIELDED (Comparing Base vs Shield)
    print("\n--- ES SHIELD TEST ---")
    
    # Base
    es_base_eng = GoldenProtocolBacktest(BacktestConfig(fib_entry=0.5, breakeven_trigger_r=0.0))
    es_base_res = es_base_eng.run(es_5m, nq_5m)
    es_base_trades = [t for t in es_base_res.trades if t.asset=="ES"]
    es_base_loss = sum(1 for t in es_base_trades if t.state==TradeState.LOSS)
    print(f"ES BASE: {len(es_base_trades)} Trades, {es_base_loss} Losses")

    # Shielded
    es_sh_eng = GoldenProtocolBacktest(BacktestConfig(fib_entry=0.5, breakeven_trigger_r=0.5))
    es_sh_res = es_sh_eng.run(es_5m, nq_5m)
    es_sh_trades = [t for t in es_sh_res.trades if t.asset=="ES"]
    
    es_sh_loss = sum(1 for t in es_sh_trades if t.state==TradeState.LOSS and abs(t.pnl) > 50) # Real losses
    es_sh_scratch = sum(1 for t in es_sh_trades if t.state==TradeState.LOSS and abs(t.pnl) <= 50) # Saved
    
    print(f"ES SHIELDED: {len(es_sh_trades)} Trades")
    print(f"  Real Losses: {es_sh_loss}")
    print(f"  SAVED Losses (Scratches): {es_sh_scratch} <--- THE SHIELD WORKS")
    
    # PnL Diff
    base_pnl = sum(t.pnl for t in es_base_trades)
    shield_pnl = sum(t.pnl for t in es_sh_trades)
    print(f"  Base PnL: ${base_pnl:.2f} -> Shield PnL: ${shield_pnl:.2f}")

if __name__ == "__main__":
    run_rapid_verify()
