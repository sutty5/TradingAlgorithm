"""
ES R:R Optimizer - Find the best Risk:Reward configuration for ES SHORT

Tests multiple fib configurations to find better R:R closer to 1:1
while maintaining high win rate.

Run with: modal run es_rr_optimizer.py
"""

import modal
import pandas as pd
import numpy as np
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime
import itertools
import json

app = modal.App("es_rr_optimizer")
vol = modal.Volume.from_name("trading-data-vol")
image = modal.Image.debian_slim().pip_install("pandas", "numpy", "databento")


# --- STRATEGY ENGINE (Inlined for Modal) ---

class TradeState(Enum):
    SCANNING = "SCANNING"
    PPI = "PPI"
    SWEEP = "SWEEP"
    PENDING = "PENDING"
    FILLED = "FILLED"
    WIN = "WIN"
    LOSS = "LOSS"
    EXPIRED = "EXPIRED"


class TradeDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class BacktestConfig:
    timeframe_minutes: int = 2
    ppi_expiry_candles: int = 12
    entry_expiry_candles: int = 7
    fib_entry: float = 0.5
    fib_stop: float = 1.15
    fib_target: float = 0.0
    es_point_value: float = 50.0
    nq_point_value: float = 20.0
    min_wick_ratio: float = 0.25
    max_atr: float = 6.0
    use_trailing_fib: bool = True
    direction_filter: str = "SHORT"  # ES is SHORT only


@dataclass
class TradeSetup:
    ppi_time: datetime
    ppi_high: float
    ppi_low: float
    asset: str
    state: TradeState = TradeState.PPI
    candles_since_ppi: int = 0
    candles_since_bos: int = 0
    sweep_time: Optional[datetime] = None
    sweep_direction: Optional[TradeDirection] = None
    sweep_extreme: Optional[float] = None
    bos_time: Optional[datetime] = None
    fib_0: Optional[float] = None
    fib_1: Optional[float] = None
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    fill_time: Optional[datetime] = None
    outcome: Optional[str] = None
    pnl: float = 0.0


def calculate_fib_levels(fib_0, fib_1, direction, config):
    fib_range = abs(fib_1 - fib_0)
    if direction == TradeDirection.SHORT:
        entry = fib_0 + config.fib_entry * fib_range
        stop = fib_0 + (config.fib_stop * fib_range)
        # Target 0.0 = impulse origin, negative = extension below
        target = fib_0 + (config.fib_target * fib_range)
    else:
        entry = fib_0 - config.fib_entry * fib_range
        stop = fib_0 - (config.fib_stop * fib_range)
        target = fib_0 - (config.fib_target * fib_range)
    return entry, stop, target


class BacktestEngine:
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.active_trades = {}
        self.completed_trades = []
    
    def run(self, es_bars: pd.DataFrame, nq_bars: pd.DataFrame) -> Dict:
        self.active_trades = {}
        self.completed_trades = []
        
        common_idx = es_bars.index.intersection(nq_bars.index)
        
        for ts in common_idx:
            es_candle = es_bars.loc[ts]
            nq_candle = nq_bars.loc[ts]
            self._process_active_trades(ts, es_candle, nq_candle)
            self._check_for_ppi(ts, es_candle, nq_candle)
        
        wins = sum(1 for t in self.completed_trades if t.state == TradeState.WIN)
        losses = sum(1 for t in self.completed_trades if t.state == TradeState.LOSS)
        total_pnl = sum(t.pnl for t in self.completed_trades)
        filled = wins + losses
        win_rate = (wins / filled * 100) if filled > 0 else 0
        
        # Calculate actual R:R from config
        rr = self.config.fib_entry / (self.config.fib_stop - self.config.fib_entry) if (self.config.fib_stop - self.config.fib_entry) > 0 else 0
        
        return {
            "wins": wins, 
            "losses": losses, 
            "filled": filled, 
            "win_rate": win_rate, 
            "pnl": total_pnl,
            "rr": rr
        }
    
    def _process_active_trades(self, ts, es_candle, nq_candle):
        for asset in list(self.active_trades.keys()):
            trade = self.active_trades[asset]
            candle = es_candle if asset == "ES" else nq_candle
            
            if trade.state == TradeState.PPI:
                self._process_ppi(trade, ts, candle)
            elif trade.state == TradeState.SWEEP:
                self._process_sweep(trade, ts, candle)
            elif trade.state == TradeState.PENDING:
                self._process_pending(trade, ts, candle)
            elif trade.state == TradeState.FILLED:
                self._process_filled(trade, ts, candle)
            
            if trade.state in (TradeState.WIN, TradeState.LOSS, TradeState.EXPIRED):
                self.completed_trades.append(trade)
                del self.active_trades[asset]
    
    def _check_for_ppi(self, ts, es_candle, nq_candle):
        es_dir = 1 if es_candle['close'] > es_candle['open'] else (-1 if es_candle['close'] < es_candle['open'] else 0)
        nq_dir = 1 if nq_candle['close'] > nq_candle['open'] else (-1 if nq_candle['close'] < nq_candle['open'] else 0)
        
        if es_dir != 0 and nq_dir != 0 and es_dir != nq_dir:
            # Only create ES trade (SHORT direction)
            if "ES" not in self.active_trades:
                self.active_trades["ES"] = TradeSetup(
                    ppi_time=ts, ppi_high=es_candle['high'], ppi_low=es_candle['low'], asset="ES"
                )
    
    def _process_ppi(self, trade, ts, candle):
        trade.candles_since_ppi += 1
        if trade.candles_since_ppi > self.config.ppi_expiry_candles:
            trade.state = TradeState.EXPIRED
            return
        
        # Short sweep only for ES
        if candle['high'] > trade.ppi_high and candle['close'] <= trade.ppi_high:
            wick_up = candle['high'] - max(candle['open'], candle['close'])
            candle_range = candle['high'] - candle['low']
            if candle_range > 0 and (wick_up / candle_range) >= self.config.min_wick_ratio:
                trade.state = TradeState.SWEEP
                trade.sweep_direction = TradeDirection.SHORT
                trade.sweep_extreme = candle['high']
                trade.fib_1 = candle['high']
    
    def _process_sweep(self, trade, ts, candle):
        if trade.sweep_direction == TradeDirection.SHORT:
            if candle['close'] < trade.ppi_low:
                trade.bos_time = ts
                trade.fib_0 = candle['low']
                e, s, t = calculate_fib_levels(trade.fib_0, trade.fib_1, trade.sweep_direction, self.config)
                trade.entry_price, trade.stop_price, trade.target_price = e, s, t
                trade.state = TradeState.PENDING
    
    def _process_pending(self, trade, ts, candle):
        trade.candles_since_bos += 1
        
        # Trailing fib
        if self.config.use_trailing_fib:
            if trade.sweep_direction == TradeDirection.SHORT and candle['low'] < trade.fib_0:
                trade.fib_0 = candle['low']
                e, s, t = calculate_fib_levels(trade.fib_0, trade.fib_1, trade.sweep_direction, self.config)
                trade.entry_price, trade.stop_price, trade.target_price = e, s, t
        
        # Fill check
        if trade.sweep_direction == TradeDirection.SHORT and candle['high'] >= trade.entry_price:
            trade.fill_time = ts
            trade.state = TradeState.FILLED
            return
        
        # Expiry
        if trade.candles_since_bos >= self.config.entry_expiry_candles:
            trade.state = TradeState.EXPIRED
    
    def _process_filled(self, trade, ts, candle):
        point_value = self.config.es_point_value
        
        if trade.sweep_direction == TradeDirection.SHORT:
            # Stop first (conservative)
            if candle['high'] >= trade.stop_price:
                trade.state = TradeState.LOSS
                trade.pnl = (trade.entry_price - trade.stop_price) * point_value
            elif candle['low'] <= trade.target_price:
                trade.state = TradeState.WIN
                trade.pnl = (trade.entry_price - trade.target_price) * point_value


# --- OPTIMIZATION CONFIGURATIONS ---

# Test ranges for ES SHORT
ENTRY_FIBS = [0.382, 0.5, 0.618]  # Shallow to deep pullback
STOP_FIBS = [0.893, 1.0, 1.15]     # Tight to wide stop
TARGET_FIBS = [0.0, -0.1, -0.236]   # Conservative to extension targets
WICK_RATIOS = [0.25, 0.35, 0.5]    # Wick filter strictness


def generate_configs():
    """Generate all test configurations."""
    configs = []
    
    for entry, stop, target, wick in itertools.product(
        ENTRY_FIBS, STOP_FIBS, TARGET_FIBS, WICK_RATIOS
    ):
        # Skip invalid configs where entry > stop
        if entry >= stop:
            continue
            
        # Calculate R:R
        risk = stop - entry
        reward = entry - target  # For short: profit when price goes down
        rr = reward / risk if risk > 0 else 0
        
        configs.append({
            'entry': entry,
            'stop': stop,
            'target': target,
            'wick': wick,
            'rr': rr
        })
    
    return configs


# --- MODAL CLOUD FUNCTIONS ---

@app.function(image=image, volumes={"/data": vol}, timeout=600, cpu=1.0, memory=2048)
def run_single_config(cfg: dict, es_bars_json: str, nq_bars_json: str) -> Dict:
    """Run a single backtest config."""
    es_bars = pd.read_json(es_bars_json, orient='split')
    nq_bars = pd.read_json(nq_bars_json, orient='split')
    
    config = BacktestConfig(
        timeframe_minutes=2,
        entry_expiry_candles=7,
        fib_entry=cfg['entry'],
        fib_stop=cfg['stop'],
        fib_target=cfg['target'],
        min_wick_ratio=cfg['wick'],
        direction_filter="SHORT"
    )
    
    engine = BacktestEngine(config)
    result = engine.run(es_bars, nq_bars)
    
    return {
        'entry': cfg['entry'],
        'stop': cfg['stop'],
        'target': cfg['target'],
        'wick': cfg['wick'],
        'config_rr': cfg['rr'],
        **result
    }


@app.function(image=image, volumes={"/data": vol}, timeout=3600, cpu=4.0, memory=16384)
def prepare_and_dispatch():
    """Load data and dispatch to 100 workers."""
    import databento as db
    
    print("Loading tick data from volume...")
    dbn_path = "/data/trades_es_nq_2025-09-21_2025-12-20.dbn"
    
    store = db.DBNStore.from_file(dbn_path)
    df = store.to_df()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    
    print(f"Loaded {len(df):,} ticks")
    
    # Split by asset and resample to 2m
    es_ticks = df[df['symbol'].str.contains("ES")]
    nq_ticks = df[df['symbol'].str.contains("NQ")]
    
    es_bars = es_ticks['price'].resample('2min').agg(
        open='first', high='max', low='min', close='last'
    ).dropna()
    nq_bars = nq_ticks['price'].resample('2min').agg(
        open='first', high='max', low='min', close='last'
    ).dropna()
    
    print(f"ES bars: {len(es_bars)}, NQ bars: {len(nq_bars)}")
    
    # Serialize for workers
    es_json = es_bars.to_json(orient='split', date_format='iso')
    nq_json = nq_bars.to_json(orient='split', date_format='iso')
    
    # Generate configs
    configs = generate_configs()
    print(f"\nTesting {len(configs)} configurations...")
    
    # Dispatch to workers
    futures = []
    for cfg in configs:
        future = run_single_config.remote(cfg, es_json, nq_json)
        futures.append(future)
    
    # Collect results
    results = []
    for f in futures:
        results.append(f)
    
    return results


@app.local_entrypoint()
def main():
    print("\n" + "="*80)
    print("🎯 ES R:R OPTIMIZER (100 Container Cluster)")
    print("Finding best configuration with R:R closer to 1:1")
    print("="*80 + "\n")
    
    results = prepare_and_dispatch.remote()
    
    # Sort by win rate, then by R:R closeness to 1.0
    df = pd.DataFrame(results)
    
    # Filter for profitable configs with 70%+ WR
    profitable = df[(df['win_rate'] >= 70) & (df['filled'] >= 50)]
    
    if profitable.empty:
        print("No configs with 70%+ WR and 50+ trades found.")
        print("\nTop 10 by Win Rate:")
        top = df.nlargest(10, 'win_rate')
    else:
        # Score: Penalize R:R far from 1.0
        profitable['rr_score'] = 1 - abs(profitable['config_rr'] - 1.0)
        profitable['total_score'] = profitable['win_rate'] * 0.7 + profitable['rr_score'] * 30
        top = profitable.nlargest(10, 'total_score')
    
    print("\n" + "="*80)
    print("🏆 TOP 10 ES CONFIGURATIONS")
    print("="*80)
    
    print(f"\n{'Entry':<8}{'Stop':<8}{'Target':<8}{'Wick':<8}{'R:R':<8}{'WR%':<10}{'Trades':<8}{'PnL':<12}")
    print("-" * 80)
    
    for _, row in top.iterrows():
        print(f"{row['entry']:<8.3f}{row['stop']:<8.3f}{row['target']:<8.3f}{row['wick']:<8.2f}{row['config_rr']:<8.2f}{row['win_rate']:<10.1f}{row['filled']:<8}{row['pnl']:>12,.0f}")
    
    # Best config
    if not top.empty:
        best = top.iloc[0]
        print("\n" + "="*80)
        print("🥇 RECOMMENDED ES CONFIGURATION:")
        print(f"   Entry: {best['entry']:.3f} ({best['entry']*100:.1f}%)")
        print(f"   Stop: {best['stop']:.3f} ({best['stop']*100:.1f}%)")
        print(f"   Target: {best['target']:.3f} ({best['target']*100:.1f}%)")
        print(f"   Wick: {best['wick']:.2f}")
        print(f"   R:R: {best['config_rr']:.2f}:1")
        print(f"   Win Rate: {best['win_rate']:.1f}%")
        print(f"   Trades: {best['filled']}")
        print(f"   PnL: ${best['pnl']:,.0f}")
        print("="*80)
    
    # Save all results
    df.to_json("es_rr_optimization_results.json", orient='records', indent=2)
    print("\n✅ Full results saved to es_rr_optimization_results.json")
