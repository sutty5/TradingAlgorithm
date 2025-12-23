
import pandas as pd
from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
from data_loader import load_and_prepare_data

def verify_baseline():
    print("Verifying v5.0 Baseline (NQ Short Only)...")
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    es_data, nq_data = load_and_prepare_data(dbn_path, timeframe_minutes=2)
    
    # v5.0 Settings: NQ, Short Only, 0.618, No Filters
    config = BacktestConfig(
        timeframe_minutes=2,
        fib_entry=0.618,
        fib_stop=1.0,
        fib_target=0.0,
        entry_expiry_candles=7,
        use_trend_filter=False,
        use_macro_filter=False,
        require_bb_expansion=False
    )
    
    engine = GoldenProtocolBacktest(config)
    results = engine.run(es_data, nq_data)
    
    # Filter for NQ Short Only
    # blocked hours: 8, 9, 18, 19
    blocked = [8, 9, 18, 19]
    
    filtered = []
    for t in results.trades:
        if t.asset != "NQ": continue
        if t.sweep_direction != TradeDirection.SHORT: continue # SHORT ONLY
        if t.ppi_time.hour in blocked: continue
        filtered.append(t)
        
    wins = sum(1 for t in filtered if t.state == TradeState.WIN)
    losses = sum(1 for t in filtered if t.state == TradeState.LOSS)
    total = wins + losses
    pnl = sum(t.pnl for t in filtered)
    
    print("\n--- BASELINE RESULTS (NQ Short Only) ---")
    print(f"Trades: {total}")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    wr = (wins/total*100) if total > 0 else 0
    print(f"Win Rate: {wr:.2f}%")
    print(f"PnL: ${pnl:,.2f}")

if __name__ == "__main__":
    verify_baseline()
