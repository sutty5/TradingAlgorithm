"""
Golden Protocol v4.9 - MULTI-TIMEFRAME DEEP Optimizer

Tests:
- 3 timeframes: 1min, 2min, 5min
- 2 assets: ES, NQ (optimized separately)
- Multiple direction, hour, and Fib combinations

Goal: Find the ultimate breakthrough configuration.
"""
import pandas as pd
import numpy as np
from itertools import product
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# TIMEFRAMES TO TEST
# ============================================================
TIMEFRAMES = [1, 2, 5]  # minutes

# Hour groups to test blocking
HOUR_BLOCK_OPTIONS = [
    [],  # No blocking
    [8, 9],  # Block US pre-market
    [13, 14],  # Block US open
    [18, 19, 20],  # Block late NY
    [8, 9, 18, 19],  # Block open + close
    [13, 14, 18, 19],  # Block US volatility windows
]

# Parameter space per asset
ASSET_PARAMS = {
    'direction': ['BOTH', 'SHORT_ONLY', 'LONG_ONLY'],
    'blocked_hours': HOUR_BLOCK_OPTIONS,
    'fib_entry': [0.5, 0.618],
    'fib_stop': [1.0],
    'fib_target': [0.0],
    'ppi_expiry': [10, 12],
    'entry_expiry': [5, 7],
}


@dataclass
class AssetConfig:
    """Config for a single asset."""
    asset: str
    timeframe: int
    direction: str
    blocked_hours: List[int]
    fib_entry: float
    ppi_expiry: int
    entry_expiry: int
    wins: int = 0
    losses: int = 0
    pnl: float = 0.0
    max_consec_losses: int = 0
    
    @property
    def filled(self): return self.wins + self.losses
    
    @property
    def win_rate(self): return (self.wins / self.filled * 100) if self.filled > 0 else 0
    
    @property
    def rr_ratio(self):
        risk = abs(1.0 - self.fib_entry)
        reward = abs(self.fib_entry - 0.0)
        return reward / risk if risk > 0 else 0


@dataclass
class CombinedConfig:
    """Combined ES + NQ config (can have different timeframes)."""
    es_config: Optional[AssetConfig]
    nq_config: Optional[AssetConfig]
    
    @property
    def total_wins(self):
        return (self.es_config.wins if self.es_config else 0) + (self.nq_config.wins if self.nq_config else 0)
    
    @property
    def total_losses(self):
        return (self.es_config.losses if self.es_config else 0) + (self.nq_config.losses if self.nq_config else 0)
    
    @property
    def total_pnl(self):
        return (self.es_config.pnl if self.es_config else 0) + (self.nq_config.pnl if self.nq_config else 0)
    
    @property
    def filled(self): return self.total_wins + self.total_losses
    
    @property
    def win_rate(self): return (self.total_wins / self.filled * 100) if self.filled > 0 else 0
    
    @property
    def max_consec(self):
        mcl = 0
        if self.es_config: mcl = max(mcl, self.es_config.max_consec_losses)
        if self.nq_config: mcl = max(mcl, self.nq_config.max_consec_losses)
        return mcl
    
    @property
    def score(self):
        """Score: WR (40%) + PnL (40%) + Volume (20%)"""
        pnl_norm = min(max(self.total_pnl / 25000, -1), 1)
        vol_norm = min(self.filled / 200, 1)
        wr_bonus = max(0, self.win_rate - 55) * 0.5  # Bonus for 55%+
        return (self.win_rate * 0.4) + (pnl_norm * 40) + (vol_norm * 20) + wr_bonus


def run_timeframe_optimization(dbn_path: str, timeframe: int, asset: str) -> List[AssetConfig]:
    """Run optimization for a single asset at a specific timeframe."""
    from data_loader import load_and_prepare_data
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
    
    # Load data at this timeframe
    es_data, nq_data = load_and_prepare_data(dbn_path, timeframe_minutes=timeframe)
    
    results = []
    
    # Pre-run backtests
    fib_configs = list(product(
        ASSET_PARAMS['fib_entry'],
        [1.0],  # fib_stop
        [0.0],  # fib_target
        ASSET_PARAMS['ppi_expiry'],
        ASSET_PARAMS['entry_expiry']
    ))
    
    backtest_cache = {}
    for fib_e, fib_s, fib_t, ppi_exp, entry_exp in fib_configs:
        config = BacktestConfig(
            fib_entry=fib_e, fib_stop=fib_s, fib_target=fib_t,
            ppi_expiry_candles=ppi_exp, entry_expiry_candles=entry_exp,
        )
        engine = GoldenProtocolBacktest(config)
        bt_results = engine.run(es_data, nq_data)
        cache_key = (fib_e, ppi_exp, entry_exp)
        backtest_cache[cache_key] = bt_results.trades
    
    # Apply filters
    for cache_key, trades in backtest_cache.items():
        fib_e, ppi_exp, entry_exp = cache_key
        
        for direction in ASSET_PARAMS['direction']:
            for blocked_hours in ASSET_PARAMS['blocked_hours']:
                filtered = []
                for t in trades:
                    if t.asset != asset:
                        continue
                    if direction == 'SHORT_ONLY' and t.sweep_direction == TradeDirection.LONG:
                        continue
                    if direction == 'LONG_ONLY' and t.sweep_direction == TradeDirection.SHORT:
                        continue
                    if t.ppi_time and t.ppi_time.hour in blocked_hours:
                        continue
                    filtered.append(t)
                
                wins = sum(1 for t in filtered if t.state == TradeState.WIN)
                losses = sum(1 for t in filtered if t.state == TradeState.LOSS)
                pnl = sum(t.pnl for t in filtered)
                
                if wins + losses < 10:
                    continue
                
                max_cl = cl = 0
                for t in filtered:
                    if t.state == TradeState.LOSS:
                        cl += 1
                        max_cl = max(max_cl, cl)
                    elif t.state == TradeState.WIN:
                        cl = 0
                
                cfg = AssetConfig(
                    asset=asset, timeframe=timeframe, direction=direction,
                    blocked_hours=list(blocked_hours), fib_entry=fib_e,
                    ppi_expiry=ppi_exp, entry_expiry=entry_exp,
                    wins=wins, losses=losses, pnl=pnl, max_consec_losses=max_cl,
                )
                results.append(cfg)
    
    # Sort by score
    def cfg_score(c):
        pnl_norm = min(max(c.pnl / 10000, -1), 1)
        vol_norm = min(c.filled / 100, 1)
        return (c.win_rate * 0.5) + (pnl_norm * 30) + (vol_norm * 20)
    
    results.sort(key=cfg_score, reverse=True)
    return results


def run_full_optimization():
    """Run full multi-timeframe, multi-asset optimization."""
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    
    print("="*80)
    print("  GOLDEN PROTOCOL v4.9 - MULTI-TIMEFRAME DEEP OPTIMIZER")
    print("="*80)
    
    all_es_configs = []
    all_nq_configs = []
    
    for tf in TIMEFRAMES:
        print(f"\n[TIMEFRAME: {tf}min]")
        print("-"*40)
        
        # ES
        print(f"  Optimizing ES at {tf}m...")
        es_cfgs = run_timeframe_optimization(dbn_path, tf, 'ES')
        print(f"    Found {len(es_cfgs)} valid configs")
        all_es_configs.extend(es_cfgs)
        
        # NQ
        print(f"  Optimizing NQ at {tf}m...")
        nq_cfgs = run_timeframe_optimization(dbn_path, tf, 'NQ')
        print(f"    Found {len(nq_cfgs)} valid configs")
        all_nq_configs.extend(nq_cfgs)
    
    # Sort all configs
    def cfg_score(c):
        pnl_norm = min(max(c.pnl / 10000, -1), 1)
        vol_norm = min(c.filled / 100, 1)
        return (c.win_rate * 0.5) + (pnl_norm * 30) + (vol_norm * 20)
    
    all_es_configs.sort(key=cfg_score, reverse=True)
    all_nq_configs.sort(key=cfg_score, reverse=True)
    
    # Print top asset configs
    print()
    print("="*80)
    print("  TOP ES CONFIGURATIONS (All Timeframes)")
    print("="*80)
    print(f"{'Rank':>4} | {'TF':>3} | {'WR':>6} | {'PnL':>10} | {'W/L':>7} | {'MCL':>3} | Dir | Hours | Fib")
    print("-"*80)
    for i, c in enumerate(all_es_configs[:20], 1):
        hrs = ','.join(map(str, c.blocked_hours)) if c.blocked_hours else 'None'
        if len(hrs) > 10: hrs = hrs[:8] + '..'
        print(f"{i:>4} | {c.timeframe:>2}m | {c.win_rate:>5.1f}% | ${c.pnl:>9,.0f} | {c.wins:>3}/{c.losses:<3} | {c.max_consec_losses:>3} | {c.direction[:5]:>5} | {hrs:<10} | {c.fib_entry}")
    
    print()
    print("="*80)
    print("  TOP NQ CONFIGURATIONS (All Timeframes)")
    print("="*80)
    print(f"{'Rank':>4} | {'TF':>3} | {'WR':>6} | {'PnL':>10} | {'W/L':>7} | {'MCL':>3} | Dir | Hours | Fib")
    print("-"*80)
    for i, c in enumerate(all_nq_configs[:20], 1):
        hrs = ','.join(map(str, c.blocked_hours)) if c.blocked_hours else 'None'
        if len(hrs) > 10: hrs = hrs[:8] + '..'
        print(f"{i:>4} | {c.timeframe:>2}m | {c.win_rate:>5.1f}% | ${c.pnl:>9,.0f} | {c.wins:>3}/{c.losses:<3} | {c.max_consec_losses:>3} | {c.direction[:5]:>5} | {hrs:<10} | {c.fib_entry}")
    
    # Find best combined configs
    print("\nFinding best combined configurations...")
    top_es = [c for c in all_es_configs if c.win_rate >= 55][:30]
    top_nq = [c for c in all_nq_configs if c.win_rate >= 55][:30]
    
    combined = []
    for es_cfg in [None] + top_es:
        for nq_cfg in [None] + top_nq:
            if es_cfg is None and nq_cfg is None:
                continue
            c = CombinedConfig(es_config=es_cfg, nq_config=nq_cfg)
            if c.win_rate >= 55 and c.filled >= 50:
                combined.append(c)
    
    combined.sort(key=lambda c: c.score, reverse=True)
    
    # Print combined results
    print()
    print("="*90)
    print("  TOP 25 COMBINED ES + NQ CONFIGURATIONS (BREAKTHROUGH CANDIDATES)")
    print("="*90)
    print()
    print(f"{'#':>3} | {'WR':>6} | {'PnL':>10} | {'Trades':>6} | {'MCL':>3} | ES Config | NQ Config")
    print("-"*90)
    
    for i, c in enumerate(combined[:25], 1):
        es_desc = "NONE"
        nq_desc = "NONE"
        if c.es_config:
            es_desc = f"{c.es_config.timeframe}m {c.es_config.direction[:3]} {c.es_config.win_rate:.0f}%"
        if c.nq_config:
            nq_desc = f"{c.nq_config.timeframe}m {c.nq_config.direction[:3]} {c.nq_config.win_rate:.0f}%"
        print(f"{i:>3} | {c.win_rate:>5.1f}% | ${c.total_pnl:>9,.0f} | {c.filled:>6} | {c.max_consec:>3} | {es_desc:>15} | {nq_desc:>15}")
    
    # Save results
    data = []
    for c in combined:
        row = {
            'combined_wr': c.win_rate,
            'combined_pnl': c.total_pnl,
            'combined_trades': c.filled,
            'combined_wins': c.total_wins,
            'combined_losses': c.total_losses,
            'max_consec_losses': c.max_consec,
            'score': c.score,
        }
        if c.es_config:
            row.update({
                'es_tf': c.es_config.timeframe,
                'es_dir': c.es_config.direction,
                'es_hours': str(c.es_config.blocked_hours),
                'es_fib': c.es_config.fib_entry,
                'es_wr': c.es_config.win_rate,
                'es_pnl': c.es_config.pnl,
                'es_trades': c.es_config.filled,
            })
        if c.nq_config:
            row.update({
                'nq_tf': c.nq_config.timeframe,
                'nq_dir': c.nq_config.direction,
                'nq_hours': str(c.nq_config.blocked_hours),
                'nq_fib': c.nq_config.fib_entry,
                'nq_wr': c.nq_config.win_rate,
                'nq_pnl': c.nq_config.pnl,
                'nq_trades': c.nq_config.filled,
            })
        data.append(row)
    
    df = pd.DataFrame(data)
    df.to_csv('optimization_v49_multitf.csv', index=False)
    print(f"\nSaved {len(combined)} results to optimization_v49_multitf.csv")
    
    # Print THE BEST
    if combined:
        best = combined[0]
        print()
        print("="*80)
        print("  === BREAKTHROUGH v4.9 CONFIGURATION ===")
        print("="*80)
        print()
        print(f"COMBINED WIN RATE: {best.win_rate:.1f}%")
        print(f"COMBINED PNL:      ${best.total_pnl:,.2f}")
        print(f"TOTAL TRADES:      {best.total_wins}W / {best.total_losses}L = {best.filled}")
        print(f"MAX CONSEC LOSSES: {best.max_consec}")
        print()
        
        if best.es_config:
            es = best.es_config
            print(f"ES Config ({es.timeframe}m):")
            print(f"  Direction:     {es.direction}")
            print(f"  Blocked Hours: {es.blocked_hours}")
            print(f"  Fib Entry:     {es.fib_entry}")
            print(f"  Win Rate:      {es.win_rate:.1f}%  ({es.wins}W/{es.losses}L)")
            print(f"  PnL:           ${es.pnl:,.2f}")
        else:
            print("ES: DISABLED")
        
        print()
        
        if best.nq_config:
            nq = best.nq_config
            print(f"NQ Config ({nq.timeframe}m):")
            print(f"  Direction:     {nq.direction}")
            print(f"  Blocked Hours: {nq.blocked_hours}")
            print(f"  Fib Entry:     {nq.fib_entry}")
            print(f"  Win Rate:      {nq.win_rate:.1f}%  ({nq.wins}W/{nq.losses}L)")
            print(f"  PnL:           ${nq.pnl:,.2f}")
        else:
            print("NQ: DISABLED")


if __name__ == "__main__":
    run_full_optimization()
