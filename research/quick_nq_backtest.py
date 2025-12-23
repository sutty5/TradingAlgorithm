"""
Quick NQ 5m Backtest - Compare with TradingView Results
"""

import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import load_and_prepare_data
from backtest_engine import run_backtest, BacktestConfig, TradeState, TradeDirection


def format_currency(value: float) -> str:
    if value >= 0:
        return f"${value:,.2f}"
    else:
        return f"-${abs(value):,.2f}"


def main():
    """Run NQ 5m LONG backtest (The Banker leg)."""
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    
    print("\n" + "=" * 70)
    print("  GOLDEN PROTOCOL v7.1 - NQ LONG 5m BACKTEST (Python Engine)")
    print("  Comparing against TradingView results")
    print("=" * 70)
    
    # Check if data exists
    if not Path(dbn_path).exists():
        print(f"[ERROR] Data file not found: {dbn_path}")
        sys.exit(1)
    
    # Load and prepare data at 5m timeframe
    print("\n[LOADING] Loading data at 5-minute timeframe...")
    es_data, nq_data = load_and_prepare_data(dbn_path, timeframe_minutes=5)
    
    print(f"[DATA] Loaded {len(nq_data):,} candles")
    print(f"[DATA] Date range: {nq_data.index.min()} to {nq_data.index.max()}")
    
    # =========================================================================
    # NQ LONG CONFIG ("The Banker")
    # =========================================================================
    config = BacktestConfig(
        timeframe_minutes=5,
        ppi_expiry_candles=12,
        entry_expiry_candles=10,  # c_expiry = 10
        fib_entry=0.5,
        fib_stop=1.0,
        fib_target=0.0,  # Impulse High
        min_wick_ratio=0.5,  # c_wick_min = 0.5
        max_atr=0.0,  # No ATR filter
        use_macro_filter=True,  # c_macro = true
        use_trailing_fib=True,  # The "Hidden Grail"
    )
    
    print("\n[CONFIG] NQ LONG (The Banker)")
    print(f"  Fib Entry: {config.fib_entry}")
    print(f"  Fib Stop: {config.fib_stop}")
    print(f"  Fib Target: {config.fib_target}")
    print(f"  Min Wick: {config.min_wick_ratio}")
    print(f"  Trailing Fibs: {config.use_trailing_fib}")
    print(f"  Macro Filter: {config.use_macro_filter}")
    
    # Run backtest
    print("\n[RUNNING] Running backtest...")
    results = run_backtest(es_data, nq_data, config)
    
    # =========================================================================
    # FILTER TO NQ LONG ONLY (God Mode spec)
    # =========================================================================
    nq_long_trades = [
        t for t in results.trades 
        if t.asset == "NQ" and t.sweep_direction == TradeDirection.LONG
    ]
    
    wins = sum(1 for t in nq_long_trades if t.state == TradeState.WIN)
    losses = sum(1 for t in nq_long_trades if t.state == TradeState.LOSS)
    expired = sum(1 for t in nq_long_trades if t.state == TradeState.EXPIRED)
    pnl = sum(t.pnl for t in nq_long_trades)
    
    filled = wins + losses
    win_rate = (wins / filled * 100) if filled > 0 else 0.0
    
    # =========================================================================
    # RESULTS
    # =========================================================================
    print("\n" + "=" * 70)
    print("  NQ LONG ONLY RESULTS (The Banker)")
    print("=" * 70)
    print(f"\n[TRADE STATISTICS]")
    print(f"  Total Setups:      {len(nq_long_trades):,}")
    print(f"  Entry Fills:       {filled:,}")
    print(f"  Expired:           {expired:,}")
    print(f"  Wins:              {wins:,}")
    print(f"  Losses:            {losses:,}")
    
    print(f"\n[PERFORMANCE METRICS]")
    print(f"  Win Rate:          {win_rate:.1f}%  {'✅ TARGET MET' if win_rate >= 74 else '⚠️ Below target'}")
    print(f"  Net PnL:           {format_currency(pnl)}")
    
    if filled > 0:
        avg_pnl = pnl / filled
        print(f"  Avg PnL/Trade:     {format_currency(avg_pnl)}")
    
    print("=" * 70)
    
    # =========================================================================
    # ALL LEGS SUMMARY (for reference)
    # =========================================================================
    print("\n[ALL GOD MODE LEGS - Full Dataset]")
    print("-" * 70)
    
    # ES SHORT
    es_short = [t for t in results.trades if t.asset == "ES" and t.sweep_direction == TradeDirection.SHORT]
    es_short_wins = sum(1 for t in es_short if t.state == TradeState.WIN)
    es_short_losses = sum(1 for t in es_short if t.state == TradeState.LOSS)
    es_short_filled = es_short_wins + es_short_losses
    es_short_wr = (es_short_wins / es_short_filled * 100) if es_short_filled > 0 else 0
    es_short_pnl = sum(t.pnl for t in es_short)
    print(f"  ES SHORT:  {es_short_filled:3} trades | WR: {es_short_wr:5.1f}% | PnL: {format_currency(es_short_pnl):>12}")
    
    # ES LONG
    es_long = [t for t in results.trades if t.asset == "ES" and t.sweep_direction == TradeDirection.LONG]
    es_long_wins = sum(1 for t in es_long if t.state == TradeState.WIN)
    es_long_losses = sum(1 for t in es_long if t.state == TradeState.LOSS)
    es_long_filled = es_long_wins + es_long_losses
    es_long_wr = (es_long_wins / es_long_filled * 100) if es_long_filled > 0 else 0
    es_long_pnl = sum(t.pnl for t in es_long)
    print(f"  ES LONG:   {es_long_filled:3} trades | WR: {es_long_wr:5.1f}% | PnL: {format_currency(es_long_pnl):>12}")
    
    # NQ SHORT
    nq_short = [t for t in results.trades if t.asset == "NQ" and t.sweep_direction == TradeDirection.SHORT]
    nq_short_wins = sum(1 for t in nq_short if t.state == TradeState.WIN)
    nq_short_losses = sum(1 for t in nq_short if t.state == TradeState.LOSS)
    nq_short_filled = nq_short_wins + nq_short_losses
    nq_short_wr = (nq_short_wins / nq_short_filled * 100) if nq_short_filled > 0 else 0
    nq_short_pnl = sum(t.pnl for t in nq_short)
    print(f"  NQ SHORT:  {nq_short_filled:3} trades | WR: {nq_short_wr:5.1f}% | PnL: {format_currency(nq_short_pnl):>12}")
    
    # NQ LONG (our target)
    print(f"  NQ LONG:   {filled:3} trades | WR: {win_rate:5.1f}% | PnL: {format_currency(pnl):>12} ⬅️ TARGET")
    
    print("-" * 70)
    
    return results


if __name__ == "__main__":
    main()
