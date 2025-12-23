"""
Golden Protocol v4.7 Backtest Engine

Implements the exact strategy logic for accurate backtesting:
- PPI (divergence) detection between ES and NQ
- Liquidity sweep detection (wick beyond + close inside)
- BOS (Break of Structure) confirmation
- Trailing Fib range calculation
- Entry fill tracking
- Outcome determination (WIN/LOSS/EXPIRED)
"""

import pandas as pd
import numpy as np
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from datetime import datetime


class TradeState(Enum):
    """Trade lifecycle states"""
    SCANNING = "SCANNING"      # Looking for PPI
    PPI = "PPI"                # Divergence detected, looking for sweep
    SWEEP = "SWEEP"            # Sweep detected, looking for BOS
    PENDING = "PENDING"        # BOS confirmed, waiting for entry fill
    FILLED = "FILLED"          # Entry filled, tracking outcome
    WIN = "WIN"                # Target hit
    LOSS = "LOSS"              # Stop hit
    EXPIRED = "EXPIRED"        # Entry not filled within expiry window


class TradeDirection(Enum):
    """Trade direction"""
    LONG = "LONG"    # Bullish - sweep of low, expecting up
    SHORT = "SHORT"  # Bearish - sweep of high, expecting down

class EntryMode(Enum):
    """Entry Logic Mode"""
    FIB_RETRACE = "FIB"       # Standard: Wait for retrace to 0.618/0.5
    SWEEP_LIMIT = "SWEEP"     # Aggressive: Place Limit immediately at Sweep Level (Betting on re-test of wick)
    BREAKOUT = "BREAKUP"      # Inverted: If price breaks PPI level, trade WITH the break (Trend Following)


@dataclass
class TradeSetup:
    """Represents a trade setup from PPI to outcome"""
    ppi_time: datetime
    ppi_es_dir: int           # +1 green, -1 red
    ppi_nq_dir: int
    ppi_high: float           # PPI candle high (for sweeps)
    ppi_low: float            # PPI candle low (for sweeps)
    asset: str                # "ES" or "NQ" - which asset triggered
    
    # Sweep info
    sweep_time: Optional[datetime] = None
    sweep_direction: Optional[TradeDirection] = None
    sweep_extreme: Optional[float] = None  # Wick extreme (fib_1)
    
    # BOS info
    bos_time: Optional[datetime] = None
    bos_extreme: Optional[float] = None  # BOS candle extreme (initial fib_0)
    
    # Trailing Fib range
    fib_0: Optional[float] = None  # Trailing end (target direction)
    fib_1: Optional[float] = None  # Locked end (sweep extreme)
    
    # Entry info
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    fill_time: Optional[datetime] = None
    
    # Tracking
    state: TradeState = TradeState.PPI
    candles_since_ppi: int = 0
    candles_since_bos: int = 0
    
    # Outcome
    outcome: Optional[str] = None
    outcome_time: Optional[datetime] = None
    outcome: Optional[str] = None
    outcome_time: Optional[datetime] = None
    pnl: float = 0.0
    breakeven_active: bool = False


@dataclass
class BacktestConfig:
    """Configuration for backtest parameters"""
    timeframe_minutes: int = 2
    ppi_expiry_candles: int = 12      # Candles after PPI to look for sweep
    entry_expiry_candles: int = 7      # Candles after BOS to fill entry
    fib_entry: float = 0.5             # Entry at 50% retracement
    fib_stop: float = 1.0              # Stop at sweep extreme
    fib_target: float = 0.0            # Target at impulse end
    es_point_value: float = 50.0       # $50 per point for ES
    nq_point_value: float = 20.0       # $20 per point for NQ
    
    # v5.0 "Outside the Box" Logic
    use_trend_filter: bool = False     # If True, only trade in direction of EMA
    trend_ema_period: int = 50         # 50 or 200
    min_atr: float = 0.0               # Minimum volatility required
    max_atr: float = 0.0               # Maximum volatility allowed (0.0 = disabled)
    min_wick_ratio: float = 0.0        # Minimum sweep wick ratio
    min_rvol: float = 0.0              # Minimum relative volume
    breakeven_trigger_r: float = 0.0   # If > 0, move stop to BE at this R-multiple
    
    # v6.0 Engineering
    use_macro_filter: bool = False     # If True, trade only in direction of 1H Trend
    require_bb_expansion: bool = False # If True, require BB Width expansion
    entry_mode: str = "FIB"            # FIB, SWEEP, BREAKUP


@dataclass
class BacktestResults:
    """Container for backtest results"""
    trades: List[TradeSetup] = field(default_factory=list)
    
    @property
    def filled_trades(self) -> List[TradeSetup]:
        """Trades that got entry fills (excludes EXPIRED)"""
        return [t for t in self.trades if t.state in (TradeState.WIN, TradeState.LOSS)]
    
    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.state == TradeState.WIN)
    
    @property
    def losses(self) -> int:
        return sum(1 for t in self.trades if t.state == TradeState.LOSS)
    
    @property
    def expired(self) -> int:
        return sum(1 for t in self.trades if t.state == TradeState.EXPIRED)
    
    @property
    def win_rate(self) -> float:
        filled = self.wins + self.losses
        return (self.wins / filled * 100) if filled > 0 else 0.0
    
    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)
    
    @property
    def max_consecutive_wins(self) -> int:
        return self._max_consecutive(TradeState.WIN)
    
    @property
    def max_consecutive_losses(self) -> int:
        return self._max_consecutive(TradeState.LOSS)
    
    def _max_consecutive(self, state: TradeState) -> int:
        max_streak = 0
        current_streak = 0
        for t in self.filled_trades:
            if t.state == state:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        return max_streak


def get_candle_direction(candle: pd.Series) -> int:
    """Get candle direction: +1 green, -1 red, 0 doji"""
    if candle['close'] > candle['open']:
        return 1
    elif candle['close'] < candle['open']:
        return -1
    return 0


def calculate_fib_levels(
    fib_0: float, 
    fib_1: float, 
    direction: TradeDirection,
    config: BacktestConfig
) -> Tuple[float, float, float]:
    """
    Calculate entry, stop, target from Fib range.
    
    For LONG (bullish): fib_0 is high (target up), fib_1 is low (sweep low)
    For SHORT (bearish): fib_0 is low (target down), fib_1 is high (sweep high)
    
    Returns: (entry, stop, target)
    """
    fib_range = abs(fib_1 - fib_0)
    
    if direction == TradeDirection.SHORT:
        # Bearish
        if config.entry_mode == "SWEEP":
            # SWEEP MODE: Limit at Sweep High (Retest)
            # Stop: 1.0 (Sweep High) ?? No, if we enter AT Sweep High, stop must be higher.
            # Stop: 1.272 Ext? Or Fixed points? 
            # Let's use 10 points for now for "Sniper" retest. Or Fib Extension 1.272.
            # IMPOSSIBLE RISK FREE? No.
            # Let's say Stop is Sweep High + (Range * 0.272)
            fib_ext = fib_1 + (fib_range * 0.272)
            entry = fib_1 # Enter at the top
            stop = fib_ext
            target = fib_0
            
        elif config.entry_mode == "BREAKUP":
            # BREAKOUT MODE: We trade the BREAK of the PPI High.
            # Entry: PPI High + Filter?
            # Stop: PPI Low? Or midpoint?
            # This logic is fundamentally different (Trend Following).
            # Let's stick to Reversion logic for now (SWEEP/FIB).
            entry = fib_0 + config.fib_entry * fib_range
            stop = fib_1
            target = fib_0 
            
        else:
            # FIB MODE (Standard)
            entry = fib_0 + config.fib_entry * fib_range   # 0.5 fib
            stop = fib_1                                    # 1.0 fib (sweep extreme)
            target = fib_0                                  # 0.0 fib (impulse end)

    else:
        # Bullish
        if config.entry_mode == "SWEEP":
            # SWEEP MODE: Limit at Sweep Low
            fib_ext = fib_1 - (fib_range * 0.272)
            entry = fib_1 
            stop = fib_ext
            target = fib_0
            
        else:
            # FIB MODE (Standard)
            entry = fib_0 - config.fib_entry * fib_range   # 0.5 fib
            stop = fib_1                                    # 1.0 fib (sweep extreme)
            target = fib_0                                  # 0.0 fib (impulse end)
    
    return entry, stop, target


class GoldenProtocolBacktest:
    """
    Backtest engine implementing Golden Protocol v4.7 strategy.
    
    Strategy phases:
    1. PPI: ES and NQ close in opposite directions (divergence)
    2. SWEEP: Price wicks beyond PPI high/low but closes inside
    3. BOS: Price closes beyond the opposite level (confirmation)
    4. PENDING: Waiting for entry fill at 0.5 Fib
    5. FILLED: Entry filled, tracking to WIN/LOSS
    """
    
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self.results = BacktestResults()
        self.active_trades: Dict[str, TradeSetup] = {}  # Active setup per asset
    
    def run(
        self, 
        es_data: pd.DataFrame, 
        nq_data: pd.DataFrame
    ) -> BacktestResults:
        """
        Run backtest on aligned ES and NQ data.
        
        Args:
            es_data: ES OHLCV DataFrame with DatetimeIndex
            nq_data: NQ OHLCV DataFrame with DatetimeIndex (aligned with ES)
            
        Returns:
            BacktestResults with all trade outcomes
        """
        self.results = BacktestResults()
        self.active_trades = {}
        
        print(f"Running backtest on {len(es_data):,} candles...")
        
        for i, timestamp in enumerate(es_data.index):
            es_candle = es_data.loc[timestamp]
            nq_candle = nq_data.loc[timestamp]
            
            # Process existing active trades first
            self._process_active_trades(timestamp, es_candle, nq_candle)
            
            # Check for new PPI (only if no active trade on an asset)
            self._check_for_ppi(timestamp, es_candle, nq_candle)
        
        # Mark any remaining active trades as expired
        for asset, trade in list(self.active_trades.items()):
            trade.state = TradeState.EXPIRED
            trade.outcome = "EXPIRED"
            self.results.trades.append(trade)
        
        self.active_trades.clear()
        
        print(f"Backtest complete. {len(self.results.trades)} trade setups found.")
        
        return self.results
    
    def _process_active_trades(
        self, 
        timestamp: datetime, 
        es_candle: pd.Series, 
        nq_candle: pd.Series
    ):
        """Process all active trade setups for this candle."""
        for asset in list(self.active_trades.keys()):
            trade = self.active_trades[asset]
            candle = es_candle if asset == "ES" else nq_candle
            
            if trade.state == TradeState.PPI:
                self._process_ppi_phase(trade, timestamp, candle)
            elif trade.state == TradeState.SWEEP:
                self._process_sweep_phase(trade, timestamp, candle)
            elif trade.state == TradeState.PENDING:
                self._process_pending_phase(trade, timestamp, candle)
            elif trade.state == TradeState.FILLED:
                self._process_filled_phase(trade, timestamp, candle)
            
            # Check if trade is complete
            if trade.state in (TradeState.WIN, TradeState.LOSS, TradeState.EXPIRED):
                self.results.trades.append(trade)
                del self.active_trades[asset]
    
    def _check_for_ppi(
        self, 
        timestamp: datetime, 
        es_candle: pd.Series, 
        nq_candle: pd.Series
    ):
        """Check for PPI (divergence) condition on this candle."""
        es_dir = get_candle_direction(es_candle)
        nq_dir = get_candle_direction(nq_candle)
        
        # Skip if no clear direction on either
        if es_dir == 0 or nq_dir == 0:
            return
            
        # Volatility Filter (ATR)
        if self.config.min_atr > 0:
            if 'atr_14' in es_candle and es_candle['atr_14'] < self.config.min_atr:
                return  # Skip low volatility

        
        # PPI = divergence (opposite directions)
        if es_dir != nq_dir:
            # Create PPI setup for both assets
            # The asset that moved COUNTER to the other gets the setup
            # ES green + NQ red = Bearish setup (sweep high expected)
            # ES red + NQ green = Bullish setup (sweep low expected)
            
            for asset, candle in [("ES", es_candle), ("NQ", nq_candle)]:
                if asset not in self.active_trades:
                    # Logic: If I am the asset moving "counter", I might be the setup.
                    # e.g. ES Green, NQ Red -> ES is bullish (maybe fake), NQ is bearish (maybe fake).
                    # Actually, the logic is: Divergence = "Crack".
                    # We create setups for BOTH and let the Price Action (Sweep) decide which one validates.
                    
                    # TREND FILTER CHECK
                    if self.config.use_trend_filter:
                        ema_col = f'ema_{self.config.trend_ema_period}'
                        if ema_col in candle:
                            ema_val = candle[ema_col]
                            close_val = candle['close']
                            
                            # Determine POTENTIAL direction
                            # If this asset is Green (+1), potential setup is SHORT (Bearish Sweep of High)
                            # If this asset is Red (-1), potential setup is LONG (Bullish Sweep of Low)
                            my_dir = es_dir if asset == "ES" else nq_dir
                            
                            if my_dir == 1: # Potential SHORT
                                if close_val > ema_val: # Price above EMA = Uptrend
                                    continue # Don't short in uptrend
                            elif my_dir == -1: # Potential LONG
                                if close_val < ema_val: # Price below EMA = Downtrend
                                    continue # Don't long in downtrend

                    trade = TradeSetup(
                        ppi_time=timestamp,
                        ppi_es_dir=es_dir,
                        ppi_nq_dir=nq_dir,
                        ppi_high=candle['high'],
                        ppi_low=candle['low'],
                        asset=asset,
                        state=TradeState.PPI
                    )
                    self.active_trades[asset] = trade
    
    def _process_ppi_phase(
        self, 
        trade: TradeSetup, 
        timestamp: datetime, 
        candle: pd.Series
    ):
        """Look for liquidity sweep after PPI."""
        trade.candles_since_ppi += 1
        
        # Check for expiry
        if trade.candles_since_ppi > self.config.ppi_expiry_candles:
            trade.state = TradeState.EXPIRED
            trade.outcome = "PPI_EXPIRED"
            return
        
        # Check for bearish sweep (sweep of high)
        # Condition: Wick above PPI high, but close inside
        if candle['high'] > trade.ppi_high and candle['close'] <= trade.ppi_high:
            # FILTER CHECK
            if self.config.max_atr > 0 and candle.get('atr_14', 0) > self.config.max_atr: return
            if self.config.min_wick_ratio > 0 and candle.get('wick_ratio_up', 0) < self.config.min_wick_ratio: return
            if self.config.min_rvol > 0 and candle.get('rvol', 0) < self.config.min_rvol: return
            
            # BB Expansion
            if self.config.require_bb_expansion and not candle.get('bb_expansion', False): return
            
            # Macro Alignment (Short requires Macro Bearish (-1))
            if self.config.use_macro_filter and candle.get('macro_trend', 0) != -1: return

            trade.sweep_time = timestamp
            trade.sweep_direction = TradeDirection.SHORT
            trade.sweep_extreme = candle['high']  # This becomes fib_1
            trade.fib_1 = candle['high']
            trade.state = TradeState.SWEEP
            return
        
        # Check for bullish sweep (sweep of low)
        # Condition: Wick below PPI low, but close inside
        if candle['low'] < trade.ppi_low and candle['close'] >= trade.ppi_low:
            # FILTER CHECK
            if self.config.max_atr > 0 and candle.get('atr_14', 0) > self.config.max_atr: return
            if self.config.min_wick_ratio > 0 and candle.get('wick_ratio_down', 0) < self.config.min_wick_ratio: return
            if self.config.min_rvol > 0 and candle.get('rvol', 0) < self.config.min_rvol: return

            # BB Expansion
            if self.config.require_bb_expansion and not candle.get('bb_expansion', False): return
            
            # Macro Alignment (Long requires Macro Bullish (1))
            if self.config.use_macro_filter and candle.get('macro_trend', 0) != 1: return
            
            trade.sweep_time = timestamp
            trade.sweep_direction = TradeDirection.LONG
            trade.sweep_extreme = candle['low']  # This becomes fib_1
            trade.fib_1 = candle['low']
            trade.state = TradeState.SWEEP
            return
    
    def _process_sweep_phase(
        self, 
        trade: TradeSetup, 
        timestamp: datetime, 
        candle: pd.Series
    ):
        """Look for BOS (Break of Structure) after sweep."""
        if trade.sweep_direction == TradeDirection.SHORT:
            # Bearish: Looking for close below PPI low
            if candle['close'] < trade.ppi_low:
                trade.bos_time = timestamp
                trade.bos_extreme = candle['low']  # Initial fib_0
                trade.fib_0 = candle['low']
                
                # Calculate initial levels
                entry, stop, target = calculate_fib_levels(
                    trade.fib_0, trade.fib_1, trade.sweep_direction, self.config
                )
                trade.entry_price = entry
                trade.stop_price = stop
                trade.target_price = target
                trade.state = TradeState.PENDING
                return
        else:
            # Bullish: Looking for close above PPI high
            if candle['close'] > trade.ppi_high:
                trade.bos_time = timestamp
                trade.bos_extreme = candle['high']  # Initial fib_0
                trade.fib_0 = candle['high']
                
                # Calculate initial levels
                entry, stop, target = calculate_fib_levels(
                    trade.fib_0, trade.fib_1, trade.sweep_direction, self.config
                )
                trade.entry_price = entry
                trade.stop_price = stop
                trade.target_price = target
                trade.state = TradeState.PENDING
                return
    
    def _process_pending_phase(
        self, 
        trade: TradeSetup, 
        timestamp: datetime, 
        candle: pd.Series
    ):
        """
        Waiting for entry fill. Trailing Fib range updates here.
        Entry fill = price touches entry level.
        """
        trade.candles_since_bos += 1
        
        # First: Update trailing Fib range (before checking fill)
        if trade.sweep_direction == TradeDirection.SHORT:
            # Bearish: fib_0 trails lowest low
            if candle['low'] < trade.fib_0:
                trade.fib_0 = candle['low']
                # Recalculate levels
                entry, stop, target = calculate_fib_levels(
                    trade.fib_0, trade.fib_1, trade.sweep_direction, self.config
                )
                trade.entry_price = entry
                trade.stop_price = stop
                trade.target_price = target
        else:
            # Bullish: fib_0 trails highest high
            if candle['high'] > trade.fib_0:
                trade.fib_0 = candle['high']
                # Recalculate levels
                entry, stop, target = calculate_fib_levels(
                    trade.fib_0, trade.fib_1, trade.sweep_direction, self.config
                )
                trade.entry_price = entry
                trade.stop_price = stop
                trade.target_price = target
        
        # Check for entry fill (price touches entry level)
        if trade.sweep_direction == TradeDirection.SHORT:
            # SHORT: Entry filled when price goes UP to entry level
            if candle['high'] >= trade.entry_price:
                trade.fill_time = timestamp
                trade.state = TradeState.FILLED
                # Lock the Fib range at fill
                return
        else:
            # LONG: Entry filled when price goes DOWN to entry level
            if candle['low'] <= trade.entry_price:
                trade.fill_time = timestamp
                trade.state = TradeState.FILLED
                return
        
        # Check for expiry if no fill
        if trade.candles_since_bos >= self.config.entry_expiry_candles:
            trade.state = TradeState.EXPIRED
            trade.outcome = "ENTRY_EXPIRED"
    
    def _process_filled_phase(
        self, 
        trade: TradeSetup, 
        timestamp: datetime, 
        candle: pd.Series
    ):
        """
        Entry is filled, now tracking for WIN or LOSS.
        Check STOP first (conservative) if both hit on same candle.
        """
        # Breakeven Logic
        if self.config.breakeven_trigger_r > 0 and not trade.breakeven_active:
            risk = abs(trade.entry_price - trade.stop_price)
            if trade.sweep_direction == TradeDirection.SHORT:
                be_trigger = trade.entry_price - (risk * self.config.breakeven_trigger_r)
                if candle['low'] <= be_trigger:
                    trade.stop_price = trade.entry_price
                    trade.breakeven_active = True
            else:
                be_trigger = trade.entry_price + (risk * self.config.breakeven_trigger_r)
                if candle['high'] >= be_trigger:
                    trade.stop_price = trade.entry_price
                    trade.breakeven_active = True

        point_value = (
            self.config.es_point_value if trade.asset == "ES" 
            else self.config.nq_point_value
        )
        
        if trade.sweep_direction == TradeDirection.SHORT:
            # SHORT trade: Target is below (fib_0), Stop is above (fib_1)
            stop_hit = candle['high'] >= trade.stop_price
            target_hit = candle['low'] <= trade.target_price
            
            # Conservative: Check stop first
            if stop_hit:
                trade.state = TradeState.LOSS
                trade.outcome = "LOSS"
                trade.outcome_time = timestamp
                # PnL = entry - stop (negative for loss)
                trade.pnl = (trade.entry_price - trade.stop_price) * point_value
            elif target_hit:
                trade.state = TradeState.WIN
                trade.outcome = "WIN"
                trade.outcome_time = timestamp
                # PnL = entry - target (positive for win since target < entry for short)
                trade.pnl = (trade.entry_price - trade.target_price) * point_value
        else:
            # LONG trade: Target is above (fib_0), Stop is below (fib_1)
            stop_hit = candle['low'] <= trade.stop_price
            target_hit = candle['high'] >= trade.target_price
            
            # Conservative: Check stop first
            if stop_hit:
                trade.state = TradeState.LOSS
                trade.outcome = "LOSS"
                trade.outcome_time = timestamp
                # PnL = stop - entry (negative for loss)
                trade.pnl = (trade.stop_price - trade.entry_price) * point_value
            elif target_hit:
                trade.state = TradeState.WIN
                trade.outcome = "WIN"
                trade.outcome_time = timestamp
                # PnL = target - entry (positive for win)
                trade.pnl = (trade.target_price - trade.entry_price) * point_value


def run_backtest(
    es_data: pd.DataFrame, 
    nq_data: pd.DataFrame,
    config: Optional[BacktestConfig] = None
) -> BacktestResults:
    """
    Convenience function to run Golden Protocol backtest.
    
    Args:
        es_data: ES OHLCV DataFrame
        nq_data: NQ OHLCV DataFrame (aligned with ES)
        config: Optional configuration overrides
        
    Returns:
        BacktestResults with all metrics
    """
    engine = GoldenProtocolBacktest(config)
    return engine.run(es_data, nq_data)


if __name__ == "__main__":
    # Test with sample data
    print("Backtest engine module loaded successfully.")
    print(f"States: {[s.value for s in TradeState]}")
    print(f"Directions: {[d.value for d in TradeDirection]}")
