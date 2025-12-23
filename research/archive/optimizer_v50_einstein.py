
"""
Golden Protocol v5.0 - EINSTEIN DEEP FLIGHT Optimizer

Tests "Outside the Box" Logic:
- Trend Filtering (EMA 50/200)
- Dynamic Breakeven (0.5 R)
- Standard Filters (Hours, Direction, Fib)
- EINSTEIN METRICS: Wick Ratio, RVOL, ATR Constraints

Goal: Find the "Breakthrough" (70% WR + High Volume).
"""
import pandas as pd
import numpy as np
import shutil
from pathlib import Path
from itertools import product
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# PARAMETER SPACE
# ============================================================
TIMEFRAMES = [2]  # Focus on key TFs

# Optimization Parameters
# Common
COMMON_PARAMS = {
    'direction': ['BOTH'], 
    'blocked_hours': [[], [8, 9, 18, 19]], 
    'fib_entry': [0.618], # Confirmed best
    'entry_expiry': [7],
    'min_wick_ratio': [0.0, 0.25, 0.35],
    'min_rvol': [0.0, 1.0],
}

# Asset Specific Overrides
PARAMS_ES = {
    **COMMON_PARAMS,
    'trend_filter': [False], # ES is mean reverting usually
    'breakeven_r': [0.5], # Protect profit
    'max_atr': [0.0, 4.0, 6.0], # Filter chop/news
    'min_atr': [0.0],
}

PARAMS_NQ = {
    **COMMON_PARAMS,
    'trend_filter': [True, False], # NQ trends hard
    'trend_ema': [50],
    'breakeven_r': [0.0, 0.5],
    'max_atr': [0.0],
    'min_atr': [0.0, 12.0, 15.0], # Filter low vol
}

@dataclass
class AssetConfig:
    """Config for a single asset."""
    asset: str
    timeframe: int
    direction: str
    blocked_hours: List[int]
    fib_entry: float
    trend_filter: bool
    breakeven_r: float
    min_wick_ratio: float
    min_rvol: float
    min_atr: float
    max_atr: float
    wins: int = 0
    losses: int = 0
    pnl: float = 0.0
    max_consec_losses: int = 0
    
    @property
    def filled(self): return self.wins + self.losses
    
    @property
    def win_rate(self): return (self.wins / self.filled * 100) if self.filled > 0 else 0

@dataclass
class CombinedConfig:
    """Combined ES + NQ config."""
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
        """Score: Goal is 70% WR + High Volume (>1:1 R:R is hard coded in engine)"""
        if self.win_rate < 50: return 0 
        
        # We want PnL and Frequency
        pnl_score = self.total_pnl / 1000 # $1k = 1 point
        vol_score = self.filled * 2
        wr_score = (self.win_rate - 50) * 10
        
        return pnl_score + vol_score + wr_score


def run_timeframe_optimization(dbn_path: str, timeframe: int, asset: str) -> List[AssetConfig]:
    """Run optimization for a single asset with v5.0 logic."""
    from data_loader import load_and_prepare_data
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState
    
    # Load data (Cached)
    es_data, nq_data = load_and_prepare_data(dbn_path, timeframe_minutes=timeframe)
    
    results = []
    
    # Select Params
    P = PARAMS_ES if asset == 'ES' else PARAMS_NQ
    
    # Generate Exec Configs
    # keys: trend_filter, trend_ema(NQ only), breakeven_r, min_wick, min_rvol, min_atr, max_atr
    
    keys = ['fib_entry', 'entry_expiry', 'breakeven_r', 'min_wick_ratio', 'min_rvol', 'min_atr', 'max_atr', 'trend_filter']
    if 'trend_ema' in P: keys.append('trend_ema')
    
    # Create product iterator
    lists = [P[k] for k in keys]
    configs = list(product(*lists))
    
    print(f"    Testing {len(configs)} variances for {asset} {timeframe}m...")
    
    for values in configs:
        # Unpack
        kv = dict(zip(keys, values))
        
        # Logic check: EMA only if Trend Filter
        trend_ema = kv.get('trend_ema', 50) # Default for ES
        if not kv['trend_filter'] and 'trend_ema' in kv and trend_ema == 200: 
            continue # Skip redundant false checks
            
        config = BacktestConfig(
            fib_entry=kv['fib_entry'], 
            fib_stop=1.0, 
            fib_target=0.0,
            ppi_expiry_candles=12, 
            entry_expiry_candles=kv['entry_expiry'],
            use_trend_filter=kv['trend_filter'],
            trend_ema_period=trend_ema,
            breakeven_trigger_r=kv['breakeven_r'],
            min_atr=kv['min_atr'],
            max_atr=kv['max_atr'],
            min_wick_ratio=kv['min_wick_ratio'],
            min_rvol=kv['min_rvol']
        )
        
        engine = GoldenProtocolBacktest(config)
        bt_results = engine.run(es_data, nq_data) # Fast run with cached data + pre-calc indicators
        
        # Post-process filters (Hours)
        trades = bt_results.trades
        
        for blocked_hours in P['blocked_hours']:
            filtered = []
            for t in trades:
                if t.asset != asset: continue
                if t.ppi_time and t.ppi_time.hour in blocked_hours: continue
                filtered.append(t)
            
            # metrics
            wins = sum(1 for t in filtered if t.state == TradeState.WIN)
            losses = sum(1 for t in filtered if t.state == TradeState.LOSS)
            pnl = sum(t.pnl for t in filtered)
            
            if wins + losses < 15: continue # Minimum sample
            
            # max cl
            max_cl = cl = 0
            for t in filtered:
                if t.state == TradeState.LOSS:
                    cl += 1
                    max_cl = max(max_cl, cl)
                elif t.state == TradeState.WIN:
                    cl = 0
            
            cfg = AssetConfig(
                asset=asset, timeframe=timeframe, direction="BOTH",
                blocked_hours=list(blocked_hours), fib_entry=kv['fib_entry'],
                trend_filter=kv['trend_filter'], 
                breakeven_r=kv['breakeven_r'],
                min_wick_ratio=kv['min_wick_ratio'],
                min_rvol=kv['min_rvol'],
                min_atr=kv['min_atr'],
                max_atr=kv['max_atr'],
                wins=wins, losses=losses, pnl=pnl, max_consec_losses=max_cl
            )
            results.append(cfg)

    # Sort
    results.sort(key=lambda c: c.pnl, reverse=True)
    return results[:50] # Top 50


def run_full_optimization():
    # 0. Clear Cache (Disabled to use cached 2m data)
    # print("Clearing stale cache...")
    # cache_dir = Path("data/cache")
    # if cache_dir.exists():
    #     for f in cache_dir.glob("*.parquet"):
    #         f.unlink()
    
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    print("="*80)
    print("  v5.1 EINSTEIN HYPER-OPTIMIZATION RUN")
    print("="*80)
    
    all_es = []
    all_nq = []
    
    for tf in TIMEFRAMES:
        print(f"\nScanning {tf}m Timeframe...")
        print("  Optimizing ES...")
        all_es.extend(run_timeframe_optimization(dbn_path, tf, 'ES'))
        print("  Optimizing NQ...")
        all_nq.extend(run_timeframe_optimization(dbn_path, tf, 'NQ'))
        
    print(f"\nFound {len(all_es)} ES configs and {len(all_nq)} NQ configs.")
    
    # Combined optimization
    print("\nFinding Golden Combinations...")
    combined = []
    
    top_es = sorted(all_es, key=lambda c: c.win_rate, reverse=True)[:50]
    top_nq = sorted(all_nq, key=lambda c: c.win_rate, reverse=True)[:50]
    
    for es in [None] + top_es:
        for nq in [None] + top_nq:
            if not es and not nq: continue
            
            c = CombinedConfig(es_config=es, nq_config=nq)
            # Filter for Grail candidates
            if c.filled >= 30 and c.win_rate > 40: 
                combined.append(c)
                
    combined.sort(key=lambda c: c.score, reverse=True)
    
    # Print Results
    print("\n" + "="*80)
    print("  TOP EINSTEIN BREAKTHROUGH CANDIDATES")
    print("="*80)
    print(f"{'#':>2} | {'WR':>6} | {'PnL':>10} | {'Trades':>6} | {'MCL':>3} | ES Details | NQ Details")
    print("-" * 80)
    
    results_data = []
    
    for i, c in enumerate(combined[:25], 1):
        es_str = "OFF"
        if c.es_config:
            W = c.es_config.min_wick_ratio
            R = c.es_config.min_rvol
            es_str = f"{c.es_config.timeframe}m W>{W} V>{R} {c.es_config.win_rate:.0f}%"
            
        nq_str = "OFF"
        if c.nq_config:
            W = c.nq_config.min_wick_ratio
            R = c.nq_config.min_rvol
            nq_str = f"{c.nq_config.timeframe}m W>{W} V>{R} {c.nq_config.win_rate:.0f}%"
            
        print(f"{i:>2} | {c.win_rate:>5.1f}% | ${c.total_pnl:>9,.0f} | {c.filled:>6} | {c.max_consec:>3} | {es_str:<25} | {nq_str:<25}")

        # Save data row
        row = {
            'combined_wr': c.win_rate,
            'combined_pnl': c.total_pnl,
            'combined_trades': c.filled,
            'max_consec_losses': c.max_consec,
            'es_config': str(c.es_config) if c.es_config else "None",
            'nq_config': str(c.nq_config) if c.nq_config else "None"
        }
        results_data.append(row)
        
    pd.DataFrame(results_data).to_csv('optimization_v51_einstein.csv', index=False)
    print("\nResults saved to optimization_v51_einstein.csv")

if __name__ == "__main__":
    run_full_optimization()
