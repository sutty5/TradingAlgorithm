"""Verify Honest Ground Truth (Self-Contained Logic) - Dec 18 Trade"""
import modal
from modal import App, Image, Volume
import sys

APP_NAME = "verify-honest-run-v6"
VOLUME_NAME = "trading-data-vol"
REMOTE_DATA_DIR = "/root/data"
REMOTE_DBN_PATH = f"{REMOTE_DATA_DIR}/trades_es_nq_2025-09-21_2025-12-20.dbn"

image = (
    Image.debian_slim()
    .pip_install("pandas", "numpy", "databento")
    .add_local_file("backtest_engine.py", remote_path="/root/app/backtest_engine.py")
)

app = App(APP_NAME)
volume = Volume.from_name(VOLUME_NAME, create_if_missing=True)

@app.function(
    image=image, 
    volumes={REMOTE_DATA_DIR: volume}, 
    timeout=600, 
    cpu=1.0
)
def run_verification():
    import pandas as pd
    import numpy as np
    import databento as db
    from pathlib import Path
    from typing import Tuple
    import sys
    sys.path.append("/root/app")
    
    # ---------------------------------------------------------
    # INLINED DATA LOADER LOGIC TO FORCE FIX
    # ---------------------------------------------------------
    def load_dbn_file(filepath: str) -> pd.DataFrame:
        print(f"Reading {filepath}...")
        store = db.DBNStore.from_file(filepath)
        df = store.to_df()
        return df

    def filter_by_symbol(df: pd.DataFrame, symbol_prefix: str) -> pd.DataFrame:
        if 'symbol' in df.columns:
            mask = df['symbol'].str.startswith(symbol_prefix)
            return df[mask].copy()
        elif df.index.names and 'symbol' in df.index.names:
            df = df.reset_index()
            mask = df['symbol'].str.startswith(symbol_prefix)
            return df[mask].copy()
        for col in df.columns:
            if 'symbol' in col.lower():
                mask = df[col].str.startswith(symbol_prefix)
                return df[mask].copy()
        raise ValueError("Symbol column not found")

    def aggregate_to_ohlcv(df: pd.DataFrame, timeframe_minutes: int = 2) -> pd.DataFrame:
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'ts_event' in df.columns: df = df.set_index('ts_event')
            elif 'timestamp' in df.columns: df = df.set_index('timestamp')
        
        price_col = 'price' if 'price' in df.columns else 'last_price'
        rule = f'{timeframe_minutes}min'
        ohlcv = pd.DataFrame()
        ohlcv['open'] = df[price_col].resample(rule).first()
        ohlcv['high'] = df[price_col].resample(rule).max()
        ohlcv['low'] = df[price_col].resample(rule).min()
        ohlcv['close'] = df[price_col].resample(rule).last()
        ohlcv['volume'] = df[price_col].resample(rule).count() # Trade count proxy
        return ohlcv.dropna(subset=['open', 'close'])

    def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
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
        # Wick
        candle_range = df['high'] - df['low']
        body_top = df[['open', 'close']].max(axis=1)
        body_bottom = df[['open', 'close']].min(axis=1)
        df['wick_ratio_up'] = (df['high'] - body_top) / candle_range
        
        # --- MACRO CONTEXT (FIXED) ---
        df_1h = df.resample('1h').last()
        df_1h['ema_1h_50'] = df_1h['close'].ewm(span=50, adjust=False).mean()
        df_1h['macro_trend'] = np.where(df_1h['close'] > df_1h['ema_1h_50'], 1, -1)
        
        # CRITICAL FIX: Shift by 1
        df_1h_shifted = df_1h.shift(1)
        df['macro_trend'] = df_1h_shifted['macro_trend'].reindex(df.index, method='ffill')
        
        return df

    def load_and_prepare_data_v6(filepath, timeframe_minutes=2):
        raw_df = load_dbn_file(filepath)
        es_raw = filter_by_symbol(raw_df, 'ES')
        nq_raw = filter_by_symbol(raw_df, 'NQ')
        es_ohlcv = aggregate_to_ohlcv(es_raw, timeframe_minutes)
        nq_ohlcv = aggregate_to_ohlcv(nq_raw, timeframe_minutes)
        
        common_idx = es_ohlcv.index.intersection(nq_ohlcv.index)
        es_ohlcv = es_ohlcv.loc[common_idx]
        nq_ohlcv = nq_ohlcv.loc[common_idx]
        
        es_ohlcv = add_technical_indicators(es_ohlcv)
        nq_ohlcv = add_technical_indicators(nq_ohlcv)
        return es_ohlcv, nq_ohlcv

    # ---------------------------------------------------------
    # MAIN VERIFICATION
    # ---------------------------------------------------------
    output = []
    def log(msg): print(msg); output.append(str(msg))
    
    log("\n" + "="*80); log("VERIFYING HONEST LOGIC v6 (INLINED)"); log("="*80)
    
    es_data, nq_data = load_and_prepare_data_v6(REMOTE_DBN_PATH, timeframe_minutes=2)
    
    # Filter to Dec 18
    es_day = es_data['2025-12-18':'2025-12-18']
    nq_day = nq_data['2025-12-18':'2025-12-18']
    
    log(f"Data points: {len(es_day)}")
    
    log("\n--- Macro Trend Check (12:50 - 13:15) ---")
    window = es_day.between_time('12:50', '13:15')
    for idx, row in window.iterrows():
        log(f"{idx} | Rate: {row['close']:.2f} | Macro: {row['macro_trend']} | WickUp: {row['wick_ratio_up']:.2f}")

    from backtest_engine import GoldenProtocolBacktest, BacktestConfig
    
    class DebugBacktest(GoldenProtocolBacktest):
        def _process_ppi_phase(self, trade, timestamp, candle):
             super()._process_ppi_phase(trade, timestamp, candle)
            
    config = BacktestConfig(
        timeframe_minutes=2,
        entry_expiry_candles=15,
        fib_entry=0.5, 
        fib_stop=1.0, 
        fib_target=0.0,
        min_wick_ratio=0.25,
        max_atr=6.0,
        use_macro_filter=True, # EXPECT 2m to respect this
        use_trailing_fib=True
    )
    
    log("\n--- Running Backtest ---")
    engine = DebugBacktest(config)
    res = engine.run(es_day, nq_day)
    
    log(f"\nTrades found: {len(res.trades)}")
    for t in res.trades:
        if '12:5' in str(t.ppi_time) or '13:0' in str(t.ppi_time):
             log(f"RELEVANT TRADE: Fill: {t.fill_time} | Dir: {t.sweep_direction} | State: {t.state}")
        
    return output

@app.local_entrypoint()
def main():
    output = run_verification.remote()
    with open("research/verify_honest_result.txt", "w") as f:
        f.write("\n".join(output))
    print("\n".join(output))
