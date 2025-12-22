"""
Run Golden Protocol v4.7 Backtest

Main script to execute the backtest on historical data and output results.
"""

import sys
from pathlib import Path
from datetime import datetime

from data_loader import load_and_prepare_data
from backtest_engine import run_backtest, BacktestConfig, TradeState


def format_currency(value: float) -> str:
    """Format value as currency string."""
    if value >= 0:
        return f"${value:,.2f}"
    else:
        return f"-${abs(value):,.2f}"


def print_results_summary(results, title: str = "BACKTEST RESULTS"):
    """Print formatted backtest results summary."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)
    
    total_trades = len(results.trades)
    filled_trades = results.wins + results.losses
    
    print(f"\n[TRADE STATISTICS]")
    print(f"  Total Setups:        {total_trades:,}")
    print(f"  Entry Fills:         {filled_trades:,}")
    print(f"  Expired (no fill):   {results.expired:,}")
    print(f"  Wins:                {results.wins:,}")
    print(f"  Losses:              {results.losses:,}")
    
    print(f"\n[PERFORMANCE METRICS]")
    print(f"  Win Rate:            {results.win_rate:.1f}%")
    print(f"  Net PnL:             {format_currency(results.total_pnl)}")
    print(f"  Max Consecutive Wins:   {results.max_consecutive_wins}")
    print(f"  Max Consecutive Losses: {results.max_consecutive_losses}")
    
    # Per-trade average
    if filled_trades > 0:
        avg_pnl = results.total_pnl / filled_trades
        print(f"  Avg PnL per Trade:   {format_currency(avg_pnl)}")
    
    print("=" * 60)


def print_asset_breakdown(results):
    """Print results broken down by asset (ES vs NQ)."""
    print("\n[BREAKDOWN BY ASSET]")
    print("-" * 50)
    
    for asset in ["ES", "NQ"]:
        asset_trades = [t for t in results.trades if t.asset == asset]
        wins = sum(1 for t in asset_trades if t.state == TradeState.WIN)
        losses = sum(1 for t in asset_trades if t.state == TradeState.LOSS)
        expired = sum(1 for t in asset_trades if t.state == TradeState.EXPIRED)
        pnl = sum(t.pnl for t in asset_trades)
        
        filled = wins + losses
        win_rate = (wins / filled * 100) if filled > 0 else 0.0
        
        print(f"\n  {asset}:")
        print(f"    Setups: {len(asset_trades):,}  |  Fills: {filled:,}  |  Expired: {expired:,}")
        print(f"    Wins: {wins:,}  |  Losses: {losses:,}  |  Win Rate: {win_rate:.1f}%")
        print(f"    Net PnL: {format_currency(pnl)}")


def print_direction_breakdown(results):
    """Print results broken down by direction (LONG vs SHORT)."""
    print("\n[BREAKDOWN BY DIRECTION]")
    print("-" * 50)
    
    from backtest_engine import TradeDirection
    
    for direction in [TradeDirection.LONG, TradeDirection.SHORT]:
        dir_trades = [t for t in results.trades if t.sweep_direction == direction]
        wins = sum(1 for t in dir_trades if t.state == TradeState.WIN)
        losses = sum(1 for t in dir_trades if t.state == TradeState.LOSS)
        expired = sum(1 for t in dir_trades if t.state == TradeState.EXPIRED)
        pnl = sum(t.pnl for t in dir_trades)
        
        filled = wins + losses
        win_rate = (wins / filled * 100) if filled > 0 else 0.0
        
        label = "(BULL)" if direction == TradeDirection.LONG else "(BEAR)"
        print(f"\n  {direction.value} {label}:")
        print(f"    Setups: {len(dir_trades):,}  |  Fills: {filled:,}  |  Expired: {expired:,}")
        print(f"    Wins: {wins:,}  |  Losses: {losses:,}  |  Win Rate: {win_rate:.1f}%")
        print(f"    Net PnL: {format_currency(pnl)}")


def save_trade_log(results, filepath: str = "backtest_trades.csv"):
    """Save detailed trade log to CSV."""
    import pandas as pd
    
    trades_data = []
    for t in results.trades:
        trades_data.append({
            'ppi_time': t.ppi_time,
            'asset': t.asset,
            'direction': t.sweep_direction.value if t.sweep_direction else None,
            'sweep_time': t.sweep_time,
            'bos_time': t.bos_time,
            'fill_time': t.fill_time,
            'outcome_time': t.outcome_time,
            'entry_price': t.entry_price,
            'stop_price': t.stop_price,
            'target_price': t.target_price,
            'state': t.state.value,
            'outcome': t.outcome,
            'pnl': t.pnl,
        })
    
    df = pd.DataFrame(trades_data)
    df.to_csv(filepath, index=False)
    print(f"\n[FILE] Trade log saved to: {filepath}")


def main():
    """Main entry point for backtest."""
    # Configuration
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    timeframe = 2  # 2-minute candles (as per v4.7 optimization)
    
    print("\n*** GOLDEN PROTOCOL v4.7 BACKTEST ***")
    print("=" * 60)
    print(f"Data file: {dbn_path}")
    print(f"Timeframe: {timeframe} minutes")
    print(f"Strategy: PPI -> Sweep -> BOS -> Entry Fill -> WIN/LOSS")
    print(f"Fib Levels: Entry=0.5, Stop=1.0, Target=0.0 (1:1 R:R)")
    print("=" * 60)
    
    # Check if data exists
    if not Path(dbn_path).exists():
        print(f"[ERROR] Data file not found: {dbn_path}")
        sys.exit(1)
    
    # Load and prepare data
    print("\n[LOADING] Loading data (this may take a few minutes)...")
    es_data, nq_data = load_and_prepare_data(dbn_path, timeframe_minutes=timeframe)
    
    # Run backtest
    print("\n[RUNNING] Running backtest...")
    config = BacktestConfig(timeframe_minutes=timeframe)
    results = run_backtest(es_data, nq_data, config)
    
    # Print results
    print_results_summary(results, "GOLDEN PROTOCOL v4.7 - 3 MONTH BACKTEST")
    print_asset_breakdown(results)
    print_direction_breakdown(results)
    
    # Save trade log
    save_trade_log(results)
    
    # Print date range
    print(f"\n[DATE RANGE] {es_data.index.min()} to {es_data.index.max()}")
    
    return results


if __name__ == "__main__":
    main()
