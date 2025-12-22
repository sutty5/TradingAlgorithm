"""
Golden Protocol v5.0 - EINSTEIN DEEP FLIGHT Optimizer

Tests "Outside the Box" Logic:
- Trend Filtering (EMA 50/200)
- Dynamic Breakeven (0.5 R)
- Standard Filters (Hours, Direction, Fib)

Goal: Find the "Breakthrough" (70% WR + High Volume).
"""
import pandas as pd
import numpy as np
from itertools import product
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# PARAMETER SPACE
# ============================================================
TIMEFRAMES = [2, 5]  # Focus on key TFs

# Optimization Parameters
PARAMS = {
    'direction': ['BOTH'], # Trend filter handles bias
    'blocked_hours': [[], [8, 9, 18, 19]], # Use best known + open
    'fib_entry': [0.5, 0.618],
    'trend_filter': [False, True],
    'trend_ema': [50, 200], # Only used if trend_filter=True
    'breakeven_r': [0.0, 0.5], # 0.0=Off, 0.5=Move to BE at 0.5R
    'ppi_expiry': [12],
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
    trend_filter: bool
    trend_ema: int
    breakeven_r: float
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
        """Score: Goal is 70% WR + High Volume"""
        pnl_norm = min(max(self.total_pnl / 25000, -1), 1)
        vol_norm = min(self.filled / 200, 1)
        
        # Exponential Bonus for High Win Rate
        wr_bonus = 0
        if self.win_rate >= 60: wr_bonus += (self.win_rate - 60) * 2
        if self.win_rate >= 70: wr_bonus += (self.win_rate - 70) * 5
        
        # Base Score
        return (self.win_rate * 0.5) + (pnl_norm * 50) + (vol_norm * 20) + wr_bonus


def run_timeframe_optimization(dbn_path: str, timeframe: int, asset: str) -> List[AssetConfig]:
    """Run optimization for a single asset with v5.0 logic."""
    from data_loader import load_and_prepare_data
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
    
    # Load data
    es_data, nq_data = load_and_prepare_data(dbn_path, timeframe_minutes=timeframe)
    
    results = []
    
    # Generate configurations
    # We must run backtests for logic params (Trend, BE) because they change trade OUTCOMES, not just filter them.
    # Unlike hours/direction which can be filtered post-hoc, Trend/BE change the trade flow.
    # We will group by "Execution Params" vs "Filter Params".
    
    # Execution Params: Fib, Trend Filter, Trend EMA, Breakeven
    exec_configs = list(product(
        PARAMS['fib_entry'],
        PARAMS['trend_filter'],
        PARAMS['trend_ema'],
        PARAMS['breakeven_r'],
        PARAMS['entry_expiry']
    ))
    
    print(f"    Testing {len(exec_configs)} execution variances...")
    
    # Memoization not as easy here due to logic changes, but we can batch.
    # Actually, we have to run the engine for each Logic Combo.
    
    for fib_e, use_trend, trend_ema, be_r, entry_exp in exec_configs:
        # Skip invalid combos (e.g. trend_ema doesn't matter if use_trend=False)
        if not use_trend and trend_ema == 200: continue # optimization: only run False once per EMA
        
        config = BacktestConfig(
            fib_entry=fib_e, 
            fib_stop=1.0, 
            fib_target=0.0,
            ppi_expiry_candles=12, 
            entry_expiry_candles=entry_exp,
            use_trend_filter=use_trend,
            trend_ema_period=trend_ema,
            breakeven_trigger_r=be_r
        )
        
        engine = GoldenProtocolBacktest(config)
        bt_results = engine.run(es_data, nq_data)
        
        # Post-process filters (Hours, Direction)
        trades = bt_results.trades
        
        for blocked_hours in PARAMS['blocked_hours']:
            # Direction is always "BOTH" in this run as trend filter handles bias, 
            # but we can check if SHORT_ONLY/LONG_ONLY helps too?
            # User wants simplified "Breakthrough". Let's stick to BOTH to let trend filter work.
            
            filtered = []
            for t in trades:
                if t.asset != asset: continue
                if t.ppi_time and t.ppi_time.hour in blocked_hours: continue
                filtered.append(t)
            
            # metrics
            wins = sum(1 for t in filtered if t.state == TradeState.WIN)
            losses = sum(1 for t in filtered if t.state == TradeState.LOSS)
            pnl = sum(t.pnl for t in filtered)
            
            if wins + losses < 10: continue
            
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
                blocked_hours=list(blocked_hours), fib_entry=fib_e,
                trend_filter=use_trend, trend_ema=trend_ema if use_trend else 0,
                breakeven_r=be_r,
                wins=wins, losses=losses, pnl=pnl, max_consec_losses=max_cl
            )
            results.append(cfg)

    # Sort
    results.sort(key=lambda c: c.pnl, reverse=True)
    return results[:50] # Return top 50 per asset per TF


def run_full_optimization():
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    print("="*80)
    print("  v5.0 EINSTEIN DEEP FLIGHT - OPTIMIZATION RUN")
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
    
    top_es = sorted(all_es, key=lambda c: c.win_rate, reverse=True)[:30]
    top_nq = sorted(all_nq, key=lambda c: c.win_rate, reverse=True)[:30]
    
    for es in [None] + top_es:
        for nq in [None] + top_nq:
            if not es and not nq: continue
            
            c = CombinedConfig(es_config=es, nq_config=nq)
            # Filter for Grail candidates
            if c.filled >= 40: # Minimum volume
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
            trend = f"EMA{c.es_config.trend_ema}" if c.es_config.trend_filter else "NoTrend"
            be = f"BE@{c.es_config.breakeven_r}" if c.es_config.breakeven_r > 0 else "NoBE"
            es_str = f"{c.es_config.timeframe}m {trend} {be} {c.es_config.win_rate:.0f}%"
            
        nq_str = "OFF"
        if c.nq_config:
            trend = f"EMA{c.nq_config.trend_ema}" if c.nq_config.trend_filter else "NoTrend"
            be = f"BE@{c.nq_config.breakeven_r}" if c.nq_config.breakeven_r > 0 else "NoBE"
            nq_str = f"{c.nq_config.timeframe}m {trend} {be} {c.nq_config.win_rate:.0f}%"
            
        print(f"{i:>2} | {c.win_rate:>5.1f}% | ${c.total_pnl:>9,.0f} | {c.filled:>6} | {c.max_consec:>3} | {es_str:<25} | {nq_str:<25}")

        # Save data row
        row = {
            'combined_wr': c.win_rate,
            'combined_pnl': c.total_pnl,
            'combined_trades': c.filled,
            'max_consec_losses': c.max_consec,
            'es_config': str(c.es_config) if c.es_config else "One",
            'nq_config': str(c.nq_config) if c.nq_config else "None"
        }
        results_data.append(row)
        
    pd.DataFrame(results_data).to_csv('optimization_v50_einstein.csv', index=False)
    print("\nResults saved to optimization_v50_einstein.csv")

if __name__ == "__main__":
    run_full_optimization()
