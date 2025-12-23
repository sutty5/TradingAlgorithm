"""
v5.0 Einstein Verification Script

Runs the exact v5.0 Hybrid Configuration on the full 3-month dataset.
Generates detailed stats for user verification.
"""
import pandas as pd
import numpy as np
from data_loader import load_and_prepare_data
from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection

def print_stats(name, trades):
    if not trades:
        print(f"--- {name}: NO TRADES ---")
        return

    wins = [t for t in trades if t.state == TradeState.WIN]
    losses = [t for t in trades if t.state == TradeState.LOSS]
    
    # Breakeven / Scratch Analysis
    # In v5.0, a loss might be a BE. We need to check PnL.
    # If PnL is 0.0 (or very close), it's a scratch.
    scratch_trades = [t for t in trades if abs(t.pnl) < 1.0 and t.state in (TradeState.WIN, TradeState.LOSS)]
    real_wins = [t for t in wins if t not in scratch_trades]
    real_losses = [t for t in losses if t not in scratch_trades]
    
    total = len(trades)
    win_count = len(real_wins)
    loss_count = len(real_losses)
    scratch_count = len(scratch_trades) # BEs
    
    # Adjusted Win Rate (excluding scratches?) 
    # Usually traders include scratches in total but they don't count as wins or losses pnl-wise.
    # WR = Wins / (Wins + Losses).
    effective_trades = win_count + loss_count
    wr = (win_count / effective_trades * 100) if effective_trades > 0 else 0
    
    total_pnl = sum(t.pnl for t in trades)
    avg_win = np.mean([t.pnl for t in real_wins]) if real_wins else 0
    avg_loss = np.mean([t.pnl for t in real_losses]) if real_losses else 0
    
    # Max Drawdown (on equity curve)
    equity = np.cumsum([t.pnl for t in trades])
    peak = np.maximum.accumulate(equity)
    drawdown = peak - equity
    max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
    
    print(f"\n=== {name} STATISTICS ===")
    print(f"Total Trades:      {total}")
    print(f"  Wins:            {win_count}")
    print(f"  Losses:          {loss_count}")
    print(f"  Scratches (BE):  {scratch_count}  (Saved Losses!)")
    print(f"Win Rate (adj):    {wr:.2f}%")
    print(f"Net PnL:           ${total_pnl:,.2f}")
    print(f"Avg Win:           ${avg_win:,.2f}")
    print(f"Avg Loss:          ${avg_loss:,.2f}")
    print(f"Max Drawdown:      ${max_dd:,.2f}")
    print(f"Profit Factor:     {abs(sum(t.pnl for t in real_wins) / sum(t.pnl for t in real_losses)) if real_losses else 'Inf':.2f}")


def run_verification():
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    
    print("Loading 3-Month Data (Full Precision)...")
    # Load separate TFs
    try:
        es_2m, nq_2m = load_and_prepare_data(dbn_path, 2)
        es_5m, nq_5m = load_and_prepare_data(dbn_path, 5)
    except Exception as e:
        print(f"Error: {e}")
        return

    # --- 1. NQ EINSTEIN (Short Only, 2m, Blocked Hours) ---
    print("\nRunning NQ Einstein (Short Only)...")
    nq_config = BacktestConfig(
        fib_entry=0.618,
        use_trend_filter=False,
        breakeven_trigger_r=0.0 # Precision mode, no shield needed
    )
    nq_engine = GoldenProtocolBacktest(nq_config)
    nq_res = nq_engine.run(es_2m, nq_2m)
    
    # Filter NQ
    nq_final = []
    blocked = [8, 9, 18, 19]
    for t in nq_res.trades:
        if t.asset == "NQ":
            if t.sweep_direction == TradeDirection.SHORT: # SHORT ONLY
                if t.ppi_time.hour not in blocked:
                    nq_final.append(t)
    
    print_stats("NQ (Einstein Sniper)", nq_final)
    
    # --- 2. ES EINSTEIN (Both, 5m, Shielded) ---
    print("\nRunning ES Einstein (Shielded)...")
    es_config = BacktestConfig(
        fib_entry=0.5,
        use_trend_filter=False,
        breakeven_trigger_r=0.5 # THE SHIELD
    )
    es_engine = GoldenProtocolBacktest(es_config)
    es_res = es_engine.run(es_5m, nq_5m)
    
    # Filter ES
    es_final = []
    for t in es_res.trades:
        if t.asset == "ES":
            # No hour blocks, Both Directions
            es_final.append(t)
            
    print_stats("ES (Shielded Grinder)", es_final)

    # --- COMBINED ---
    all_trades = sorted(nq_final + es_final, key=lambda t: t.outcome_time if t.outcome_time else t.ppi_time)
    print_stats("COMBINED EINSTEIN PORTFOLIO", all_trades)

if __name__ == "__main__":
    run_verification()
