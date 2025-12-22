"""
Golden Protocol v4.8 R&D - Multi-Variable Optimizer

Einstein mode: Exhaustive search across all tunable parameters to find
the optimal strategy configuration for maximum win rate and PnL while
maintaining R:R >= 1.0.
"""
import pandas as pd
import numpy as np
from itertools import product
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import warnings
warnings.filterwarnings('ignore')

from data_loader import load_and_prepare_data
from backtest_engine import BacktestConfig, TradeState, TradeDirection

# ============================================================
# CONFIGURABLE PARAMETER SPACE
# ============================================================

PARAM_SPACE = {
    # Direction filters
    'direction_filter': ['BOTH', 'SHORT_ONLY', 'LONG_ONLY'],
    
    # Asset filters  
    'asset_filter': ['BOTH', 'ES_ONLY', 'NQ_ONLY'],
    
    # Time-based filters (UTC hours to BLOCK)
    'blocked_hours': [
        [],  # No blocking
        [3, 4, 5],  # Block early Asia
        [8, 9, 10],  # Block US Open volatility
        [18, 19, 20],  # Block late NY
        [3, 4, 8, 9],  # Block worst hours
        [8, 9, 18, 19],  # Block open/close
    ],
    
    # Fib levels for entry
    'fib_entry': [0.382, 0.5, 0.618],
    
    # Fib levels for stop (must be > entry for shorts)
    'fib_stop': [0.893, 1.0, 1.1],
    
    # Fib levels for target
    'fib_target': [0.0, 0.1, 0.236],
    
    # PPI expiry candles
    'ppi_expiry': [8, 10, 12, 15],
    
    # Entry expiry candles
    'entry_expiry': [5, 7, 10, 12],
    
    # Minimum range size (in points) - filter tiny ranges
    'min_range_points': [0, 2, 5, 10],
    
    # Maximum range size (in points) - filter huge ranges
    'max_range_points': [50, 100, 200, 1000],  # 1000 = no limit
}


@dataclass
class OptimizationResult:
    """Result from a single parameter combination test."""
    params: Dict
    total_trades: int
    wins: int
    losses: int
    expired: int
    win_rate: float
    net_pnl: float
    avg_pnl: float
    max_consec_losses: int
    rr_ratio: float
    score: float  # Combined metric for ranking


def calculate_rr_ratio(fib_entry: float, fib_stop: float, fib_target: float) -> float:
    """
    Calculate Risk:Reward ratio from Fib levels.
    For SHORT: Entry is between target (0) and stop (1)
    Risk = |entry - stop|, Reward = |entry - target|
    """
    risk = abs(fib_stop - fib_entry)
    reward = abs(fib_entry - fib_target)
    if risk == 0:
        return 0
    return reward / risk


def run_filtered_backtest(
    es_data: pd.DataFrame,
    nq_data: pd.DataFrame,
    params: Dict
) -> OptimizationResult:
    """
    Run backtest with filtered parameters.
    This modifies the base backtest logic to apply filters.
    """
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, get_candle_direction
    
    # Create config with Fib params
    config = BacktestConfig(
        fib_entry=params['fib_entry'],
        fib_stop=params['fib_stop'],
        fib_target=params['fib_target'],
        ppi_expiry_candles=params['ppi_expiry'],
        entry_expiry_candles=params['entry_expiry'],
    )
    
    # Run base backtest
    engine = GoldenProtocolBacktest(config)
    results = engine.run(es_data, nq_data)
    
    # Apply post-filters to trades
    filtered_trades = []
    for trade in results.trades:
        # Direction filter
        if params['direction_filter'] == 'SHORT_ONLY' and trade.sweep_direction == TradeDirection.LONG:
            continue
        if params['direction_filter'] == 'LONG_ONLY' and trade.sweep_direction == TradeDirection.SHORT:
            continue
        
        # Asset filter
        if params['asset_filter'] == 'ES_ONLY' and trade.asset == 'NQ':
            continue
        if params['asset_filter'] == 'NQ_ONLY' and trade.asset == 'ES':
            continue
        
        # Time filter (blocked hours)
        if trade.ppi_time is not None:
            ppi_hour = trade.ppi_time.hour
            if ppi_hour in params['blocked_hours']:
                continue
        
        # Range size filter
        if trade.fib_0 is not None and trade.fib_1 is not None:
            range_size = abs(trade.fib_1 - trade.fib_0)
            # Normalize to points (ES ~1 point = 4 ticks, NQ ~1 point = 4 ticks)
            if trade.asset == 'ES' and range_size < params['min_range_points']:
                continue
            if trade.asset == 'NQ' and range_size < params['min_range_points']:
                continue
            if trade.asset == 'ES' and range_size > params['max_range_points']:
                continue
            if trade.asset == 'NQ' and range_size > params['max_range_points']:
                continue
        
        filtered_trades.append(trade)
    
    # Calculate metrics from filtered trades
    wins = sum(1 for t in filtered_trades if t.state == TradeState.WIN)
    losses = sum(1 for t in filtered_trades if t.state == TradeState.LOSS)
    expired = sum(1 for t in filtered_trades if t.state == TradeState.EXPIRED)
    net_pnl = sum(t.pnl for t in filtered_trades)
    
    filled = wins + losses
    win_rate = (wins / filled * 100) if filled > 0 else 0
    avg_pnl = (net_pnl / filled) if filled > 0 else 0
    
    # Max consecutive losses
    max_consec_losses = 0
    current_losses = 0
    for t in filtered_trades:
        if t.state == TradeState.LOSS:
            current_losses += 1
            max_consec_losses = max(max_consec_losses, current_losses)
        elif t.state == TradeState.WIN:
            current_losses = 0
    
    # Calculate R:R ratio
    rr = calculate_rr_ratio(params['fib_entry'], params['fib_stop'], params['fib_target'])
    
    # Score: Weighted combination of win rate and PnL
    # Prioritize: Win Rate (60%) + PnL normalized (30%) + Low consecutive losses (10%)
    pnl_normalized = min(max(net_pnl / 10000, -1), 1)  # Normalize to -1 to 1
    consec_penalty = min(max_consec_losses / 10, 1)  # Penalty for high consecutive losses
    score = (win_rate * 0.6) + (pnl_normalized * 30) + ((1 - consec_penalty) * 10)
    
    return OptimizationResult(
        params=params,
        total_trades=len(filtered_trades),
        wins=wins,
        losses=losses,
        expired=expired,
        win_rate=win_rate,
        net_pnl=net_pnl,
        avg_pnl=avg_pnl,
        max_consec_losses=max_consec_losses,
        rr_ratio=rr,
        score=score
    )


def run_optimization(
    es_data: pd.DataFrame,
    nq_data: pd.DataFrame,
    param_space: Dict = PARAM_SPACE,
    min_trades: int = 50,
    min_rr: float = 0.9
) -> List[OptimizationResult]:
    """
    Run exhaustive optimization across parameter space.
    """
    results = []
    
    # Generate all parameter combinations
    keys = list(param_space.keys())
    values = list(param_space.values())
    total_combinations = 1
    for v in values:
        total_combinations *= len(v)
    
    print(f"Testing {total_combinations:,} parameter combinations...")
    
    tested = 0
    for combo in product(*values):
        params = dict(zip(keys, combo))
        
        # Skip if R:R < min threshold
        rr = calculate_rr_ratio(params['fib_entry'], params['fib_stop'], params['fib_target'])
        if rr < min_rr:
            continue
        
        result = run_filtered_backtest(es_data, nq_data, params)
        
        # Only keep results with minimum trades
        if result.wins + result.losses >= min_trades:
            results.append(result)
        
        tested += 1
        if tested % 100 == 0:
            print(f"  Tested {tested:,} / {total_combinations:,} combinations...")
    
    # Sort by score (descending)
    results.sort(key=lambda x: x.score, reverse=True)
    
    return results


def print_top_results(results: List[OptimizationResult], top_n: int = 20):
    """Print top N results."""
    print()
    print('='*90)
    print(f'  TOP {top_n} PARAMETER COMBINATIONS')
    print('='*90)
    print()
    print(f'{"Rank":>4} | {"WinRate":>7} | {"PnL":>10} | {"W/L":>7} | {"R:R":>4} | {"MCL":>3} | {"Score":>6} | Key Params')
    print('-'*90)
    
    for i, r in enumerate(results[:top_n], 1):
        params_str = f"Dir:{r.params['direction_filter'][:5]} Hrs:{len(r.params['blocked_hours'])}blk Fib:{r.params['fib_entry']}/{r.params['fib_target']}"
        print(f'{i:>4} | {r.win_rate:>6.1f}% | ${r.net_pnl:>9,.0f} | {r.wins:>3}/{r.losses:<3} | {r.rr_ratio:>4.2f} | {r.max_consec_losses:>3} | {r.score:>6.1f} | {params_str}')


def save_results_to_csv(results: List[OptimizationResult], filepath: str = 'optimization_results_v48.csv'):
    """Save all results to CSV."""
    data = []
    for r in results:
        row = {
            'win_rate': r.win_rate,
            'net_pnl': r.net_pnl,
            'wins': r.wins,
            'losses': r.losses,
            'total_trades': r.total_trades,
            'avg_pnl': r.avg_pnl,
            'max_consec_losses': r.max_consec_losses,
            'rr_ratio': r.rr_ratio,
            'score': r.score,
            **r.params
        }
        # Convert blocked_hours list to string
        row['blocked_hours'] = str(r.params['blocked_hours'])
        data.append(row)
    
    df = pd.DataFrame(data)
    df.to_csv(filepath, index=False)
    print(f"\nSaved {len(results)} results to {filepath}")


if __name__ == "__main__":
    print("="*70)
    print("  GOLDEN PROTOCOL v4.8 - EINSTEIN MODE OPTIMIZER")
    print("="*70)
    print()
    
    # Load data
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    print("Loading data (this may take a few minutes)...")
    es_data, nq_data = load_and_prepare_data(dbn_path, timeframe_minutes=2)
    
    # Run optimization
    print()
    results = run_optimization(
        es_data, nq_data,
        param_space=PARAM_SPACE,
        min_trades=50,
        min_rr=0.9  # Require at least 0.9:1 R:R
    )
    
    # Print top results
    print_top_results(results, top_n=25)
    
    # Save all results
    save_results_to_csv(results)
    
    # Print the BEST configuration
    if results:
        best = results[0]
        print()
        print("="*70)
        print("  BEST v4.8 CONFIGURATION FOUND")
        print("="*70)
        print()
        print(f"Win Rate:    {best.win_rate:.1f}%")
        print(f"Net PnL:     ${best.net_pnl:,.2f}")
        print(f"Trades:      {best.wins}W / {best.losses}L")
        print(f"R:R Ratio:   {best.rr_ratio:.2f}")
        print(f"Max Consec Losses: {best.max_consec_losses}")
        print()
        print("Parameters:")
        for k, v in best.params.items():
            print(f"  {k}: {v}")
