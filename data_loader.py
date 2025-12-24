"""
Data Loader Module for Golden Protocol v4.7 Backtest

Reads Databento .dbn tick data and aggregates into OHLCV candles.
"""

import databento as db
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
from datetime import datetime, timedelta


import threading
import time
import sys

class LoadingHeartbeat:
    def __init__(self, message="Processing"):
        self.message = message
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._animate)
        
    def __enter__(self):
        self.thread.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_event.set()
        self.thread.join()
        sys.stdout.write(f"\r{self.message}... DONE!          \n")
        sys.stdout.flush()
        
    def _animate(self):
        chars = "/-\|"
        i = 0
        start_time = time.time()
        while not self.stop_event.is_set():
            elapsed = int(time.time() - start_time)
            sys.stdout.write(f"\r{self.message}... {chars[i % len(chars)]} ({elapsed}s)")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1

def load_dbn_file(filepath: str) -> pd.DataFrame:
    """
    Load a Databento .dbn file and return as DataFrame.
    
    Args:
        filepath: Path to .dbn file
        
    Returns:
        DataFrame with trade data
    """
    with LoadingHeartbeat(f"  [SYSTEM] Reading .dbn file"):
        store = db.DBNStore.from_file(filepath)
        
    with LoadingHeartbeat(f"  [SYSTEM] Converting to DataFrame"):
        df = store.to_df()
        
    print(f"  [SYSTEM] Loaded full dataset: {len(df):,} rows.")
    return df



def filter_by_symbol(df: pd.DataFrame, symbol_prefix: str) -> pd.DataFrame:
    """
    Filter trades by symbol prefix (ES or NQ).
    
    Args:
        df: Raw trade DataFrame
        symbol_prefix: 'ES' or 'NQ'
        
    Returns:
        Filtered DataFrame
    """
    # Symbol column may be 'symbol' or embedded in index
    if 'symbol' in df.columns:
        mask = df['symbol'].str.startswith(symbol_prefix)
        return df[mask].copy()
    elif df.index.names and 'symbol' in df.index.names:
        df = df.reset_index()
        mask = df['symbol'].str.startswith(symbol_prefix)
        return df[mask].copy()
    else:
        # Try to find symbol in column names
        for col in df.columns:
            if 'symbol' in col.lower():
                mask = df[col].str.startswith(symbol_prefix)
                return df[mask].copy()
        raise ValueError(f"Cannot find symbol column in DataFrame. Columns: {df.columns.tolist()}")


def aggregate_to_ohlcv(df: pd.DataFrame, timeframe_minutes: int = 2) -> pd.DataFrame:
    """
    Aggregate tick data to OHLCV candles.
    
    Args:
        df: DataFrame with trade data (must have 'price' and timestamp index/column)
        timeframe_minutes: Candle timeframe in minutes
        
    Returns:
        DataFrame with OHLCV data indexed by candle timestamp
    """
    # Ensure we have a datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'ts_event' in df.columns:
            df = df.set_index('ts_event')
        elif 'timestamp' in df.columns:
            df = df.set_index('timestamp')
    
    # Determine price column
    price_col = None
    for col in ['price', 'trade_price', 'last_price']:
        if col in df.columns:
            price_col = col
            break
    
    if price_col is None:
        raise ValueError(f"Cannot find price column. Columns: {df.columns.tolist()}")
    
    # Determine size column for volume
    size_col = None
    for col in ['size', 'volume', 'qty', 'quantity']:
        if col in df.columns:
            size_col = col
            break
    
    # Resample to OHLCV
    rule = f'{timeframe_minutes}min'
    
    ohlcv = pd.DataFrame()
    ohlcv['open'] = df[price_col].resample(rule).first()
    ohlcv['high'] = df[price_col].resample(rule).max()
    ohlcv['low'] = df[price_col].resample(rule).min()
    ohlcv['close'] = df[price_col].resample(rule).last()
    
    if size_col:
        ohlcv['volume'] = df[size_col].resample(rule).sum()
    else:
        ohlcv['volume'] = df[price_col].resample(rule).count()  # Use trade count
    
    # Drop rows with no trades (NaN)
    ohlcv = ohlcv.dropna(subset=['open', 'close'])
    
    return ohlcv


def load_and_prepare_data(
    filepath: str,
    timeframe_minutes: int = 2
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load .dbn file and prepare aligned ES and NQ OHLCV data.
    
    Args:
        filepath: Path to .dbn file
        timeframe_minutes: Candle timeframe in minutes
        
    Returns:
        Tuple of (es_ohlcv, nq_ohlcv) DataFrames with aligned timestamps
    """
    
    # CACHING LOGIC
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    es_cache_path = cache_dir / f"{Path(filepath).stem}_es_{timeframe_minutes}m.parquet"
    nq_cache_path = cache_dir / f"{Path(filepath).stem}_nq_{timeframe_minutes}m.parquet"
    
    if es_cache_path.exists() and nq_cache_path.exists():
        print(f"Loading cached data from {cache_dir}...")
        es_ohlcv = pd.read_parquet(es_cache_path)
        nq_ohlcv = pd.read_parquet(nq_cache_path)
        print("  Cache hit! Data loaded.")
        return es_ohlcv, nq_ohlcv
        
    print(f"Loading data from {filepath}...")
    raw_df = load_dbn_file(filepath)
    print(f"  Loaded {len(raw_df):,} raw records")
    
    # Debug: show columns and sample
    print(f"  Columns: {raw_df.columns.tolist()}")
    if hasattr(raw_df.index, 'names'):
        print(f"  Index names: {raw_df.index.names}")
    
    print("Filtering ES data...")
    es_raw = filter_by_symbol(raw_df, 'ES')
    print(f"  ES trades: {len(es_raw):,}")
    
    print("Filtering NQ data...")
    nq_raw = filter_by_symbol(raw_df, 'NQ')
    print(f"  NQ trades: {len(nq_raw):,}")
    
    print(f"Aggregating to {timeframe_minutes}-minute OHLCV...")
    es_ohlcv = aggregate_to_ohlcv(es_raw, timeframe_minutes)
    nq_ohlcv = aggregate_to_ohlcv(nq_raw, timeframe_minutes)
    
    print(f"  ES candles: {len(es_ohlcv):,}")
    print(f"  NQ candles: {len(nq_ohlcv):,}")
    
    # Align timestamps (inner join - only keep candles where both have data)
    print("Aligning ES and NQ data...")
    common_idx = es_ohlcv.index.intersection(nq_ohlcv.index)
    es_ohlcv = es_ohlcv.loc[common_idx]
    nq_ohlcv = nq_ohlcv.loc[common_idx]
    
    print(f"  Aligned candles: {len(common_idx):,}")
    print(f"  Date range: {common_idx.min()} to {common_idx.max()}")
    
    # Add technical indicators
    print("Calculating technical indicators (EMA/ATR)...")
    es_ohlcv = add_technical_indicators(es_ohlcv)
    nq_ohlcv = add_technical_indicators(nq_ohlcv)
    
    # SAVE TO CACHE
    print("Saving to cache...")
    es_ohlcv.to_parquet(es_cache_path)
    nq_ohlcv.to_parquet(nq_cache_path)
    print("  Cache saved.")
    
    return es_ohlcv, nq_ohlcv


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add EMA and ATR for logic filters."""
    # EMA
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # ATR 14
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['atr_14'] = true_range.rolling(14).mean()
    
    # RVOL (Relative Volume vs 20 period SMA)
    df['vol_ema_20'] = df['volume'].rolling(20).mean()
    df['rvol'] = df['volume'] / df['vol_ema_20']
    
    # Wick Ratios
    # Upper Wick (for Short Sweeps): High - Max(Open, Close)
    # Lower Wick (for Long Sweeps): Min(Open, Close) - Low
    candle_range = df['high'] - df['low']
    body_top = df[['open', 'close']].max(axis=1)
    body_bottom = df[['open', 'close']].min(axis=1)
    
    df['wick_ratio_up'] = (df['high'] - body_top) / candle_range
    df['wick_ratio_down'] = (body_bottom - df['low']) / candle_range
    
    # Handle div by zero
    df['wick_ratio_up'] = df['wick_ratio_up'].fillna(0.0)
    df['wick_ratio_down'] = df['wick_ratio_down'].fillna(0.0)
    df['rvol'] = df['rvol'].fillna(0.0)

    # --- MACRO CONTEXT ---
    # We want 1H Trend info on the 2m chart.
    # Resample to 1H, calc EMA, reindex back to 2m (Forward fill)
    
    # 1H Trend
    # Resample
    df_1h = df.resample('1h').last() # approximate
    df_1h['ema_1h_50'] = df_1h['close'].ewm(span=50, adjust=False).mean()
    df_1h['macro_trend'] = np.where(df_1h['close'] > df_1h['ema_1h_50'], 1, -1)
    
    # CRITICAL FIX: Shift by 1 to prevent lookahead
    # The value for 13:00-14:00 (closed 13:59) is only available at 14:00+
    # So 13:00 timestamp should get the PREVIOUS hour's trend
    df_1h_shifted = df_1h.shift(1)
    
    # Reindex back to original index (ffill)
    df['macro_trend'] = df_1h_shifted['macro_trend'].reindex(df.index, method='ffill')
    
    # Bollinger Bands (Expansion Check)
    # Standard: 20, 2
    period = 20
    std_dev = 2
    df['bb_mid'] = df['close'].rolling(window=period).mean()
    df['bb_std'] = df['close'].rolling(window=period).std()
    df['bb_upper'] = df['bb_mid'] + (df['bb_std'] * std_dev)
    df['bb_lower'] = df['bb_mid'] - (df['bb_std'] * std_dev)
    
    # BB Width (Normalized)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
    # Expansion: Is current width > recent average width?
    df['bb_width_ma'] = df['bb_width'].rolling(50).mean()
    df['bb_expansion'] = df['bb_width'] > df['bb_width_ma']

    return df


def get_candle_direction(candle: pd.Series) -> int:
    """
    Get candle direction: +1 for green (close > open), -1 for red (close < open), 0 for doji.
    """
    if candle['close'] > candle['open']:
        return 1  # Green/Bullish
    elif candle['close'] < candle['open']:
        return -1  # Red/Bearish
    else:
        return 0  # Doji


if __name__ == "__main__":
    # Test the data loader
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    
    if Path(dbn_path).exists():
        es_data, nq_data = load_and_prepare_data(dbn_path, timeframe_minutes=2)
        
        print("\n--- ES Sample ---")
        print(es_data.head(10))
        
        print("\n--- NQ Sample ---")
        print(nq_data.head(10))
    else:
        print(f"File not found: {dbn_path}")
