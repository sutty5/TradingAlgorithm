"""
Golden Protocol v4.8 R&D - FAST Optimizer

Focused parameter sweep using insights from pattern analysis.
Reduced search space to test ~5,000 high-impact combinations.
"""
import pandas as pd
import numpy as np
from itertools import product
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# FOCUSED PARAMETER SPACE (Based on Pattern Analysis)
# ============================================================

PARAM_SPACE = {
    # Direction filters - SHORT showed 57% vs LONG 48%
    'direction_filter': ['BOTH', 'SHORT_ONLY'],
    
    # Asset filters  
    'asset_filter': ['BOTH', 'ES_ONLY', 'NQ_ONLY'],
    
    # Time-based filters (UTC hours to BLOCK) - Based on analysis
    'blocked_hours': [
        [],  # No blocking
        [3, 4, 9],  # Block worst hours from analysis
        [8, 9, 18, 19],  # Block open/close volatility
        [3, 4, 8, 9, 18, 19],  # Block all worst hours
    ],
    
    # Fib entry - keeping 0.5 as baseline
    'fib_entry': [0.5, 0.618],
    
    # Fib stop
    'fib_stop': [1.0, 1.1],
    
    # Fib target - 0.0 is the current
    'fib_target': [0.0, 0.1],
    
    # PPI expiry - test extended windows
    'ppi_expiry': [10, 12, 15],
    
    # Entry expiry
    'entry_expiry': [5, 7, 10],
}

@dataclass
class OptResult:
    """Optimization result."""
    params: Dict
    wins: int
    losses: int
    win_rate: float
    net_pnl: float
    rr_ratio: float
    max_consec_losses: int
    score: float


def calculate_rr(fib_entry: float, fib_stop: float, fib_target: float) -> float:
    """Calculate Risk:Reward ratio."""
    risk = abs(fib_stop - fib_entry)
    reward = abs(fib_entry - fib_target)
    return reward / risk if risk > 0 else 0


def run_fast_optimizer():
    """Run focused optimization."""
    from data_loader import load_and_prepare_data
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
    
    print("="*70)
    print("  GOLDEN PROTOCOL v4.8 - FAST OPTIMIZER")
    print("="*70)
    
    # Load data
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    print("\nLoading data...")
    es_data, nq_data = load_and_prepare_data(dbn_path, timeframe_minutes=2)
    
    # Calculate total combinations
    total = 1
    for v in PARAM_SPACE.values():
        total *= len(v)
    print(f"\nTesting {total:,} parameter combinations...")
    
    results = []
    tested = 0
    
    # Pre-run backtests for each unique backtest config
    # Then apply filters to results
    print("\nRunning base backtests...")
    
    # Cache backtests by (ppi_expiry, entry_expiry, fib_entry, fib_stop, fib_target)
    backtest_cache = {}
    
    fib_configs = list(product(
        PARAM_SPACE['fib_entry'],
        PARAM_SPACE['fib_stop'], 
        PARAM_SPACE['fib_target'],
        PARAM_SPACE['ppi_expiry'],
        PARAM_SPACE['entry_expiry']
    ))
    
    for i, (fib_e, fib_s, fib_t, ppi_exp, entry_exp) in enumerate(fib_configs):
        rr = calculate_rr(fib_e, fib_s, fib_t)
        if rr < 0.9:  # Skip if R:R too low
            continue
            
        config = BacktestConfig(
            fib_entry=fib_e,
            fib_stop=fib_s,
            fib_target=fib_t,
            ppi_expiry_candles=ppi_exp,
            entry_expiry_candles=entry_exp,
        )
        
        engine = GoldenProtocolBacktest(config)
        bt_results = engine.run(es_data, nq_data)
        
        cache_key = (fib_e, fib_s, fib_t, ppi_exp, entry_exp)
        backtest_cache[cache_key] = bt_results.trades
        
        if (i + 1) % 10 == 0:
            print(f"  Base backtests: {i+1}/{len(fib_configs)}")
    
    print(f"\nApplying filters to {len(backtest_cache)} base backtests...")
    
    # Now apply direction/asset/time filters
    for cache_key, trades in backtest_cache.items():
        fib_e, fib_s, fib_t, ppi_exp, entry_exp = cache_key
        rr = calculate_rr(fib_e, fib_s, fib_t)
        
        for dir_filter in PARAM_SPACE['direction_filter']:
            for asset_filter in PARAM_SPACE['asset_filter']:
                for blocked_hours in PARAM_SPACE['blocked_hours']:
                    # Apply filters
                    filtered = []
                    for t in trades:
                        # Direction filter
                        if dir_filter == 'SHORT_ONLY' and t.sweep_direction == TradeDirection.LONG:
                            continue
                        if dir_filter == 'LONG_ONLY' and t.sweep_direction == TradeDirection.SHORT:
                            continue
                        
                        # Asset filter
                        if asset_filter == 'ES_ONLY' and t.asset == 'NQ':
                            continue
                        if asset_filter == 'NQ_ONLY' and t.asset == 'ES':
                            continue
                        
                        # Time filter
                        if t.ppi_time is not None and t.ppi_time.hour in blocked_hours:
                            continue
                        
                        filtered.append(t)
                    
                    # Calculate metrics
                    wins = sum(1 for t in filtered if t.state == TradeState.WIN)
                    losses = sum(1 for t in filtered if t.state == TradeState.LOSS)
                    filled = wins + losses
                    
                    if filled < 30:  # Minimum trades requirement
                        continue
                    
                    net_pnl = sum(t.pnl for t in filtered)
                    win_rate = wins / filled * 100 if filled > 0 else 0
                    
                    # Max consecutive losses
                    max_cl = cl = 0
                    for t in filtered:
                        if t.state == TradeState.LOSS:
                            cl += 1
                            max_cl = max(max_cl, cl)
                        elif t.state == TradeState.WIN:
                            cl = 0
                    
                    # Score: WR * 0.6 + PnL_norm * 0.3 + (1 - consec_penalty) * 0.1
                    pnl_norm = min(max(net_pnl / 20000, -1), 1)
                    consec_penalty = min(max_cl / 10, 1)
                    score = (win_rate * 0.6) + (pnl_norm * 30) + ((1 - consec_penalty) * 10)
                    
                    params = {
                        'direction_filter': dir_filter,
                        'asset_filter': asset_filter,
                        'blocked_hours': blocked_hours,
                        'fib_entry': fib_e,
                        'fib_stop': fib_s,
                        'fib_target': fib_t,
                        'ppi_expiry': ppi_exp,
                        'entry_expiry': entry_exp,
                    }
                    
                    results.append(OptResult(
                        params=params,
                        wins=wins,
                        losses=losses,
                        win_rate=win_rate,
                        net_pnl=net_pnl,
                        rr_ratio=rr,
                        max_consec_losses=max_cl,
                        score=score
                    ))
                    
                    tested += 1
    
    print(f"\nTested {tested:,} valid combinations")
    
    # Sort by score
    results.sort(key=lambda x: x.score, reverse=True)
    
    # Print top results
    print()
    print("="*90)
    print("  TOP 25 PARAMETER COMBINATIONS")
    print("="*90)
    print()
    print(f"{'Rank':>4} | {'WR':>6} | {'PnL':>10} | {'W/L':>7} | {'R:R':>4} | {'MCL':>3} | Direction | Asset | Blocked Hours")
    print("-"*90)
    
    for i, r in enumerate(results[:25], 1):
        blocked = ','.join(map(str, r.params['blocked_hours'])) if r.params['blocked_hours'] else 'None'
        print(f"{i:>4} | {r.win_rate:>5.1f}% | ${r.net_pnl:>9,.0f} | {r.wins:>3}/{r.losses:<3} | {r.rr_ratio:>4.2f} | {r.max_consec_losses:>3} | {r.params['direction_filter']:>9} | {r.params['asset_filter']:>5} | {blocked}")
    
    # Save to CSV
    data = []
    for r in results:
        row = {
            'win_rate': r.win_rate,
            'net_pnl': r.net_pnl,
            'wins': r.wins,
            'losses': r.losses,
            'rr_ratio': r.rr_ratio,
            'max_consec_losses': r.max_consec_losses,
            'score': r.score,
            **r.params
        }
        row['blocked_hours'] = str(r.params['blocked_hours'])
        data.append(row)
    
    df = pd.DataFrame(data)
    df.to_csv('optimization_results_v48.csv', index=False)
    print(f"\nSaved {len(results)} results to optimization_results_v48.csv")
    
    # Print BEST configuration
    if results:
        best = results[0]
        print()
        print("="*70)
        print("  BEST v4.8 CONFIGURATION FOUND")
        print("="*70)
        print()
        print(f"Win Rate:            {best.win_rate:.1f}%")
        print(f"Net PnL:             ${best.net_pnl:,.2f}")
        print(f"Trades:              {best.wins}W / {best.losses}L")
        print(f"R:R Ratio:           {best.rr_ratio:.2f}")
        print(f"Max Consec Losses:   {best.max_consec_losses}")
        print()
        print("Parameters:")
        for k, v in best.params.items():
            print(f"  {k}: {v}")
        
        return best
    
    return None


if __name__ == "__main__":
    run_fast_optimizer()
