import sys
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Ensure we can import from root
sys.path.append(os.getcwd())

from alpaca_paper_trader import BarAggregator, StrategyInstance, CONFIGS, Candle
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ALPACA_BACKTEST")

async def run_backtest():
    load_dotenv()
    # Aggressively clear all root handlers to stop other modules from printing
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    
    # Setup our clean logger
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)
    
    api_key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    
    if not api_key:
        logger.error("Missing API Keys")
        return

    logger.info("🚀 Starting 3-Month Alpaca Backtest (SPY/QQQ)...")
    
    data_client = StockHistoricalDataClient(api_key, secret)
    
    # Range: Last 90 Days
    now = datetime(2025, 12, 24, 0, 0, tzinfo=timezone.utc)
    start_dt = datetime.now(timezone.utc) - timedelta(days=90)
    
    logger.info(f"Fetching Data: {start_dt.date()} to {now.date()}")
    
    # 1. Fetch Macro Data (1H)
    logger.info("Fetching Macro (1H)...")
    # Buffer start by 5 days for EMA
    req_macro = StockBarsRequest(symbol_or_symbols="SPY", timeframe=TimeFrame(1, TimeFrameUnit.Hour), start=start_dt - timedelta(days=5), end=now, limit=10000)
    macro_df = data_client.get_stock_bars(req_macro).df.reset_index()
    
    # Process Macro
    macro_df['ema_50'] = macro_df['close'].ewm(span=50, adjust=False).mean()
    macro_df['raw_trend'] = np.where(macro_df['close'] > macro_df['ema_50'], 1, -1)
    macro_df.set_index('timestamp', inplace=True)
    
    # 2. Fetch Minute Data
    # Only fetch Market Hours to speed up? No, simpler to fetch all and filter.
    # Alpaca limit is 10,000 bars per request? Need pagination or simple large fetch?
    # get_stock_bars handles pagination automatically!
    logger.info("Fetching 1m Ticks (This may take a minute)...")
    
    req_spy = StockBarsRequest(symbol_or_symbols="SPY", timeframe=TimeFrame(1, TimeFrameUnit.Minute), start=start_dt, end=now)
    req_qqq = StockBarsRequest(symbol_or_symbols="QQQ", timeframe=TimeFrame(1, TimeFrameUnit.Minute), start=start_dt, end=now)
    
    spy_df = data_client.get_stock_bars(req_spy).df
    qqq_df = data_client.get_stock_bars(req_qqq).df
    
    if 'symbol' in spy_df.index.names: spy_df = spy_df.reset_index(level='symbol', drop=True)
    if 'symbol' in qqq_df.index.names: qqq_df = qqq_df.reset_index(level='symbol', drop=True)
    
    logger.info(f"Loaded {len(spy_df)} SPY candles and {len(qqq_df)} QQQ candles.")

    # 3. Setup Strategy
    strats = [StrategyInstance(c) for c in CONFIGS if "V8" in c.name]
    
    # 4. Data Resampling (Robust)
    logger.info("Resampling 1m data to 2m/5m...")
    
    def resample_bars(df, tf_min):
        if df.empty: return df
        # Resample: OHLCV
        # label='left', closed='left' aligns 10:00-10:02 to 10:00 index.
        agg_rule = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        res = df.resample(f'{tf_min}min', label='left', closed='left').agg(agg_rule).dropna()
        return res

    # Create Dictionary of DataFrames: [tf][symbol]
    # Ensure index is datetime
    if not isinstance(spy_df.index, pd.DatetimeIndex): spy_df.index = pd.to_datetime(spy_df.index)
    if not isinstance(qqq_df.index, pd.DatetimeIndex): qqq_df.index = pd.to_datetime(qqq_df.index)

    tf_data = {
        2: {'SPY': resample_bars(spy_df, 2), 'QQQ': resample_bars(qqq_df, 2)},
        5: {'SPY': resample_bars(spy_df, 5), 'QQQ': resample_bars(qqq_df, 5)}
    }
    
    # Validation
    logger.info(f"2m Bars: SPY={len(tf_data[2]['SPY'])}, QQQ={len(tf_data[2]['QQQ'])}")
    logger.info(f"5m Bars: SPY={len(tf_data[5]['SPY'])}, QQQ={len(tf_data[5]['QQQ'])}")

    trades = []
    
    # 5. Simulation Loop (Tick by Tick 1m)
    all_times = sorted(list(set(spy_df.index).union(set(qqq_df.index))))
    
    # Pre-extract numpy for 1m lookahead (Scanning forward for TP/SL)
    spy_np = {col: spy_df[col].values for col in ['open', 'high', 'low', 'close', 'volume']}
    qqq_np = {col: qqq_df[col].values for col in ['open', 'high', 'low', 'close', 'volume']}
    spy_idx_map = {t: i for i, t in enumerate(spy_df.index)}
    qqq_idx_map = {t: i for i, t in enumerate(qqq_df.index)}
    
    logger.info("Simulating Logic...")
    
    # Initial Account State
    current_equity = 100000.0
    buying_power = 400000.0
    
    macro_map = {} # dt (hour precision) -> Trend
    for ts, row in macro_df.iterrows():
        apply_time = ts + timedelta(hours=1)
        key = apply_time.strftime("%Y-%m-%d %H")
        macro_map[key] = int(row['raw_trend'])
        
    total_steps = len(all_times)
    processed_steps = 0
    next_check = 5 # percent

    # Debug Counters
    debug_stats = {
        'total_candles_fed': 0,
        'agg_candles_formed': {2: 0, 5: 0},
        'ppi_triggers': 0,
        'sweeps_found': 0,
        'wick_fails': 0,
        'macro_fails': 0,
        'bos_triggers': 0,
        'signals_generated': 0
    }

    for ts in all_times:
        processed_steps += 1
        pct = (processed_steps / total_steps) * 100
        if pct >= next_check:
            print(f"📊 Progress: {int(pct)}% ({processed_steps}/{total_steps})")
            next_check += 5

        hour_key = ts.strftime("%Y-%m-%d %H")
        current_macro = macro_map.get(hour_key, 0)
        
        # Check for TF closures
        for tf in [2, 5]:
            # If current 'ts' is 10:02. The 10:00-10:02 bar is complete.
            # Its label is 10:00.
            # 10:02 - 2 mins = 10:00.
            # So check if (ts - tf) exists in the resampled DF.
            
            label_ts = ts - timedelta(minutes=tf)
            
            # Fetch Candles
            row_s = tf_data[tf]['SPY'].loc[label_ts] if label_ts in tf_data[tf]['SPY'].index else None
            row_q = tf_data[tf]['QQQ'].loc[label_ts] if label_ts in tf_data[tf]['QQQ'].index else None
            
            if row_s is not None and row_q is not None:
                # Convert to Candle objects
                c_s = Candle(label_ts, row_s.open, row_s.high, row_s.low, row_s.close, row_s.volume, "SPY")
                c_q = Candle(label_ts, row_q.open, row_q.high, row_q.low, row_q.close, row_q.volume, "QQQ")
                
                # Run Logic
                for strat in strats:
                    if strat.cfg.timeframe == tf:
                        target = c_s if strat.cfg.target_symbol == "SPY" else c_q
                        ref = c_q if strat.cfg.target_symbol == "SPY" else c_s
                        
                        sig = strat.on_candles(target, ref, current_macro, current_equity, buying_power)
                        if sig:
                            debug_stats['signals_generated'] += 1
                            debug_stats['bos_triggers'] += 1
                            entry = sig['entry']
                            stop = sig['stop']
                            target_px = sig['target']
                            is_long = "BUY" in str(sig['side'])
                            qty = sig['qty']
                            
                            # Fast Forward Search with Numpy
                            sym = sig['symbol']
                            f_np = spy_np if sym == "SPY" else qqq_np
                            f_idx = spy_idx_map[ts] if sym == "SPY" else qqq_idx_map[ts]
                            
                            highs = f_np['high'][f_idx+1:]
                            lows = f_np['low'][f_idx+1:]
                            
                            filled = False
                            pnl_points = 0.0
                            
                            # Optimized outcome check
                            for i in range(len(highs)):
                                h, l = highs[i], lows[i]
                                
                                if not filled:
                                    if is_long:
                                        if l <= entry: filled = True
                                    else:
                                        if h >= entry: filled = True
                                
                                if filled:
                                    if is_long:
                                        if l <= stop: pnl_points=-abs(entry-stop); break
                                        if h >= target_px: pnl_points=abs(target_px-entry); break
                                    else:
                                        if h >= stop: pnl_points=-abs(stop-entry); break
                                        if l <= target_px: pnl_points=abs(entry-target_px); break
                                        
                            if filled:
                                trade_pnl_usd = pnl_points * qty
                                current_equity += trade_pnl_usd
                                # Re-calc BP assuming 4x leverage
                                buying_power = current_equity * 4
                                
                                trades.append({
                                    'pnl': trade_pnl_usd, 
                                    'pnl_points': pnl_points,
                                    'strat': sig['strategy'], 
                                    'time': ts,
                                    'equity': current_equity
                                })
                                    # Only log wins/losses if they happen to keep output clean, or silent
                                    # logger.info(f"TRADE {ts} | {sig['strategy']} | {outcome} | PnL: {pnl:.2f}")

    logger.info("-" * 40)
    logger.info(f"Simulation Complete. Total Trades Triggered: {len(trades)}")
    
    # Print Final Stats
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    
    if len(trades) > 0:
        wr = (len(wins) / len(trades)) * 100
        total_pnl_usd = sum(t['pnl'] for t in trades)
        final_equity = trades[-1]['equity'] if trades else current_equity # Use last equity
        
        print("\n" + "="*40)
        print("         90-DAY BACKTEST SUMMARY (RESAMPLED)")
        print("="*40)
        print(f"Total Trades:    {len(trades)}")
        print(f"Wins:            {len(wins)}")
        print(f"Losses:          {len(losses)}")
        print(f"Win Rate:        {wr:.1f}%")
        print(f"Final Equity:    ${final_equity:,.2f}")
        print(f"Total PnL (USD): ${total_pnl_usd:,.2f}")
        print("="*40)
        
        # Breakdown by strategy
        print("\nBreakdown by Strategy:")
        df = pd.DataFrame(trades)
        for name, group in df.groupby('strat'):
            g_wr = (len(group[group['pnl'] > 0]) / len(group)) * 100
            print(f"- {name:<25}: {len(group):>3} trades, {g_wr:>5.1f}% WR, ${group['pnl'].sum():>8.2f} USD")
    else:
        logger.info("No Trades Found.")

    # Print Debug Stats (Always)
    print("\n" + "="*40)
    print("         DEBUG STATS")
    print("="*40)
    print(f"Total 1m Inputs: {debug_stats['total_candles_fed']}")
    print(f"Aggregates Formed (2m): {debug_stats['agg_candles_formed'][2]}")
    print(f"Aggregates Formed (5m): {debug_stats['agg_candles_formed'][5]}")
    print(f"PPI Triggers: {debug_stats['ppi_triggers']}")
    print(f"Sweeps Found: {debug_stats['sweeps_found']}")
    print(f"Signals Generated: {debug_stats['signals_generated']}")
    print("="*40)

if __name__ == "__main__":
    asyncio.run(run_backtest())
