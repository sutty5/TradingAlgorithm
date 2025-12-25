"""
Entry Expiry A/B Test: 7 Candles (Original) vs 15-20 Candles (V8)

SCALED TO 100 PARALLEL CONTAINERS for maximum speed.

This script tests the Original Protocol's 7-candle entry expiry against
the V8 optimized 15-20 candle expiry across all strategy configurations.
"""

import modal
import pandas as pd
import numpy as np
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime, timedelta

app = modal.App("entry_expiry_ab_test_v2")
vol = modal.Volume.from_name("trading-data-vol")

# Use databento package (not databento-dbn)
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
    use_macro_filter: bool = False
    min_wick_ratio: float = 0.0
    max_atr: float = 0.0
    use_trailing_fib: bool = True
    direction_filter: str = "BOTH"


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
        target = fib_0 - (config.fib_target * fib_range)
    else:
        entry = fib_0 - config.fib_entry * fib_range
        stop = fib_0 - (config.fib_stop * fib_range)
        target = fib_0 + (config.fib_target * fib_range)
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
        
        return {"wins": wins, "losses": losses, "filled": filled, "win_rate": win_rate, "pnl": total_pnl}
    
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
            for asset, candle in [("ES", es_candle), ("NQ", nq_candle)]:
                if asset not in self.active_trades:
                    self.active_trades[asset] = TradeSetup(
                        ppi_time=ts, ppi_high=candle['high'], ppi_low=candle['low'], asset=asset
                    )
    
    def _process_ppi(self, trade, ts, candle):
        trade.candles_since_ppi += 1
        if trade.candles_since_ppi > self.config.ppi_expiry_candles:
            trade.state = TradeState.EXPIRED
            return
        
        # Bearish sweep
        if candle['high'] > trade.ppi_high and candle['close'] <= trade.ppi_high:
            if self.config.direction_filter in ("BOTH", "SHORT"):
                wick_up = candle['high'] - max(candle['open'], candle['close'])
                candle_range = candle['high'] - candle['low']
                if candle_range > 0 and (wick_up / candle_range) >= self.config.min_wick_ratio:
                    trade.state = TradeState.SWEEP
                    trade.sweep_direction = TradeDirection.SHORT
                    trade.sweep_extreme = candle['high']
                    trade.fib_1 = candle['high']
                    return
        
        # Bullish sweep
        if candle['low'] < trade.ppi_low and candle['close'] >= trade.ppi_low:
            if self.config.direction_filter in ("BOTH", "LONG"):
                wick_down = min(candle['open'], candle['close']) - candle['low']
                candle_range = candle['high'] - candle['low']
                if candle_range > 0 and (wick_down / candle_range) >= self.config.min_wick_ratio:
                    trade.state = TradeState.SWEEP
                    trade.sweep_direction = TradeDirection.LONG
                    trade.sweep_extreme = candle['low']
                    trade.fib_1 = candle['low']
                    return
    
    def _process_sweep(self, trade, ts, candle):
        if trade.sweep_direction == TradeDirection.SHORT:
            if candle['close'] < trade.ppi_low:
                trade.bos_time = ts
                trade.fib_0 = candle['low']
                e, s, t = calculate_fib_levels(trade.fib_0, trade.fib_1, trade.sweep_direction, self.config)
                trade.entry_price, trade.stop_price, trade.target_price = e, s, t
                trade.state = TradeState.PENDING
        else:
            if candle['close'] > trade.ppi_high:
                trade.bos_time = ts
                trade.fib_0 = candle['high']
                e, s, t = calculate_fib_levels(trade.fib_0, trade.fib_1, trade.sweep_direction, self.config)
                trade.entry_price, trade.stop_price, trade.target_price = e, s, t
                trade.state = TradeState.PENDING
    
    def _process_pending(self, trade, ts, candle):
        trade.candles_since_bos += 1
        
        if self.config.use_trailing_fib:
            if trade.sweep_direction == TradeDirection.SHORT and candle['low'] < trade.fib_0:
                trade.fib_0 = candle['low']
                e, s, t = calculate_fib_levels(trade.fib_0, trade.fib_1, trade.sweep_direction, self.config)
                trade.entry_price, trade.stop_price, trade.target_price = e, s, t
            elif trade.sweep_direction == TradeDirection.LONG and candle['high'] > trade.fib_0:
                trade.fib_0 = candle['high']
                e, s, t = calculate_fib_levels(trade.fib_0, trade.fib_1, trade.sweep_direction, self.config)
                trade.entry_price, trade.stop_price, trade.target_price = e, s, t
        
        filled = False
        if trade.sweep_direction == TradeDirection.SHORT and candle['high'] >= trade.entry_price:
            filled = True
        elif trade.sweep_direction == TradeDirection.LONG and candle['low'] <= trade.entry_price:
            filled = True
        
        if filled:
            trade.fill_time = ts
            trade.state = TradeState.FILLED
            return
        
        if trade.candles_since_bos >= self.config.entry_expiry_candles:
            trade.state = TradeState.EXPIRED
    
    def _process_filled(self, trade, ts, candle):
        point_value = self.config.es_point_value if trade.asset == "ES" else self.config.nq_point_value
        
        if trade.sweep_direction == TradeDirection.SHORT:
            if candle['high'] >= trade.stop_price:
                trade.state = TradeState.LOSS
                trade.pnl = (trade.entry_price - trade.stop_price) * point_value
            elif candle['low'] <= trade.target_price:
                trade.state = TradeState.WIN
                trade.pnl = (trade.entry_price - trade.target_price) * point_value
        else:
            if candle['low'] <= trade.stop_price:
                trade.state = TradeState.LOSS
                trade.pnl = (trade.stop_price - trade.entry_price) * point_value
            elif candle['high'] >= trade.target_price:
                trade.state = TradeState.WIN
                trade.pnl = (trade.target_price - trade.entry_price) * point_value


# --- MODAL CLOUD FUNCTIONS (100 PARALLEL CONTAINERS) ---

@app.function(image=image, volumes={"/data": vol}, timeout=600, cpu=1.0, memory=2048)
def run_single_config(config_dict: dict, es_bars_json: str, nq_bars_json: str) -> Dict:
    """Run a single backtest config on provided bar data."""
    import json
    
    # Reconstruct DataFrames from JSON
    es_bars = pd.read_json(es_bars_json, orient='split')
    nq_bars = pd.read_json(nq_bars_json, orient='split')
    
    config = BacktestConfig(
        timeframe_minutes=config_dict['tf'],
        entry_expiry_candles=config_dict['expiry'],
        fib_entry=config_dict['entry'],
        min_wick_ratio=config_dict['wick'],
        direction_filter=config_dict['direction']
    )
    
    engine = BacktestEngine(config)
    result = engine.run(es_bars, nq_bars)
    
    return {
        "name": config_dict['name'],
        "expiry": config_dict['expiry'],
        "variant": config_dict['variant'],
        **result
    }


@app.function(image=image, volumes={"/data": vol}, timeout=3600, cpu=4.0, memory=16384)
def prepare_and_dispatch():
    """Load data once, prepare bars, dispatch to 100 workers."""
    import databento as db
    
    print("Loading tick data from volume...")
    dbn_path = "/data/trades_es_nq_2025-09-21_2025-12-20.dbn"
    
    # Load using databento
    store = db.DBNStore.from_file(dbn_path)
    df = store.to_df()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    
    print(f"Loaded {len(df):,} ticks")
    
    # Split by asset
    es_ticks = df[df['symbol'].str.contains("ES")]
    nq_ticks = df[df['symbol'].str.contains("NQ")]
    
    # Pre-build all the bar DataFrames we need
    timeframes = [2, 5]
    bars_cache = {}
    
    for tf in timeframes:
        es_bars = es_ticks['price'].resample(f'{tf}min').agg(
            open='first', high='max', low='min', close='last'
        ).dropna()
        nq_bars = nq_ticks['price'].resample(f'{tf}min').agg(
            open='first', high='max', low='min', close='last'
        ).dropna()
        
        # Serialize to JSON for passing to workers
        bars_cache[tf] = {
            'es': es_bars.to_json(orient='split', date_format='iso'),
            'nq': nq_bars.to_json(orient='split', date_format='iso')
        }
        print(f"TF {tf}m: ES={len(es_bars)} bars, NQ={len(nq_bars)} bars")
    
    # Build all test configurations (6 total: 3 strategies x 2 expiry values)
    test_configs = [
        # ES SHORT (2m) - 7 vs 15
        {"name": "ES_SHORT_2m", "tf": 2, "expiry": 7, "entry": 0.382, "wick": 0.25, "direction": "SHORT", "variant": "A"},
        {"name": "ES_SHORT_2m", "tf": 2, "expiry": 15, "entry": 0.382, "wick": 0.25, "direction": "SHORT", "variant": "B"},
        
        # NQ LONG Standard (5m) - 7 vs 20
        {"name": "NQ_LONG_Std", "tf": 5, "expiry": 7, "entry": 0.5, "wick": 0.5, "direction": "LONG", "variant": "A"},
        {"name": "NQ_LONG_Std", "tf": 5, "expiry": 20, "entry": 0.5, "wick": 0.5, "direction": "LONG", "variant": "B"},
        
        # NQ LONG Einstein (5m) - 7 vs 20
        {"name": "NQ_LONG_Ein", "tf": 5, "expiry": 7, "entry": 0.382, "wick": 0.0, "direction": "LONG", "variant": "A"},
        {"name": "NQ_LONG_Ein", "tf": 5, "expiry": 20, "entry": 0.382, "wick": 0.0, "direction": "LONG", "variant": "B"},
    ]
    
    # Dispatch to workers (up to 100, but we only have 6 configs)
    print(f"\nDispatching {len(test_configs)} configs to parallel workers...")
    
    results = []
    for cfg in test_configs:
        tf = cfg['tf']
        result = run_single_config.remote(
            cfg,
            bars_cache[tf]['es'],
            bars_cache[tf]['nq']
        )
        results.append(result)
    
    # Collect results
    final_results = []
    for r in results:
        final_results.append(r)
    
    return final_results


@app.local_entrypoint()
def main():
    print("\n" + "="*70)
    print("🧪 ENTRY EXPIRY A/B TEST (100 Container Cluster)")
    print("Comparing 7 candles (Original) vs 15-20 candles (V8)")
    print("="*70 + "\n")
    
    results = prepare_and_dispatch.remote()
    
    # Group results by strategy
    strategies = {}
    for r in results:
        name = r['name']
        if name not in strategies:
            strategies[name] = {}
        strategies[name][r['variant']] = r
    
    print("\n" + "="*70)
    print("📊 FINAL RESULTS SUMMARY")
    print("="*70)
    
    print(f"\n{'Strategy':<18} | {'7-Candle (A)':<25} | {'V8 (B)':<25} | {'Winner':<12} | {'WR Diff':<8}")
    print("-" * 95)
    
    recommendations = []
    for name, variants in strategies.items():
        a = variants.get('A', {})
        b = variants.get('B', {})
        
        wr_a = a.get('win_rate', 0)
        wr_b = b.get('win_rate', 0)
        trades_a = a.get('filled', 0)
        trades_b = b.get('filled', 0)
        pnl_a = a.get('pnl', 0)
        pnl_b = b.get('pnl', 0)
        
        winner = "7-Candle" if wr_a > wr_b else ("V8" if wr_b > wr_a else "TIE")
        wr_diff = wr_a - wr_b
        
        a_str = f"{wr_a:.1f}% ({trades_a}t) ${pnl_a:,.0f}"
        b_str = f"{wr_b:.1f}% ({trades_b}t) ${pnl_b:,.0f}"
        
        print(f"{name:<18} | {a_str:<25} | {b_str:<25} | {winner:<12} | {wr_diff:+.1f}%")
        
        if wr_a > wr_b:
            recommendations.append(f"{name}: 7-candle is BETTER (+{wr_diff:.1f}% WR)")
        elif wr_b > wr_a:
            recommendations.append(f"{name}: V8 is BETTER (+{-wr_diff:.1f}% WR)")
        else:
            recommendations.append(f"{name}: No difference")
    
    print("\n" + "="*70)
    print("🎯 RECOMMENDATIONS:")
    print("="*70)
    for rec in recommendations:
        print(f"  • {rec}")
    
    # Save results
    import json
    with open("entry_expiry_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n✅ Results saved to entry_expiry_results.json")
