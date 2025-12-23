"""
v5.0 Einstein Logic Probe

Tests specific hypothesis configurations to validate "Outside the Box" logic.
"""
import pandas as pd
from data_loader import load_and_prepare_data
from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState

def run_probe(dbn_path):
    print("Loading Probe Data...")
    # Load 2m and 5m
    try:
        es_2m, nq_2m = load_and_prepare_data(dbn_path, 2)
        es_5m, nq_5m = load_and_prepare_data(dbn_path, 5)
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    configs_to_test = [
        # --- ES HYPOTHESES (5m) ---
        {
            "name": "ES v4.9 Baseline",
            "asset": "ES", "tf": 5, "data": (es_5m, nq_5m),
            "cfg": BacktestConfig(fib_entry=0.5, use_trend_filter=False, breakeven_trigger_r=0.0)
        },
        {
            "name": "ES + Breakeven (0.5R)",
            "asset": "ES", "tf": 5, "data": (es_5m, nq_5m),
            "cfg": BacktestConfig(fib_entry=0.5, use_trend_filter=False, breakeven_trigger_r=0.5)
        },
        {
            "name": "ES + Trend (EMA 50)",
            "asset": "ES", "tf": 5, "data": (es_5m, nq_5m),
            "cfg": BacktestConfig(fib_entry=0.5, use_trend_filter=True, trend_ema_period=50, breakeven_trigger_r=0.0)
        },
        {
            "name": "ES + Trend + BE",
            "asset": "ES", "tf": 5, "data": (es_5m, nq_5m),
            "cfg": BacktestConfig(fib_entry=0.5, use_trend_filter=True, trend_ema_period=50, breakeven_trigger_r=0.5)
        },

        # --- NQ HYPOTHESES (2m) ---
        {
            "name": "NQ v4.9 Baseline",
            "asset": "NQ", "tf": 2, "data": (es_2m, nq_2m),
            "cfg": BacktestConfig(fib_entry=0.618, use_trend_filter=False, breakeven_trigger_r=0.0)
        },
        {
            "name": "NQ + Breakeven (0.5R)",
            "asset": "NQ", "tf": 2, "data": (es_2m, nq_2m),
            "cfg": BacktestConfig(fib_entry=0.618, use_trend_filter=False, breakeven_trigger_r=0.5)
        },
        {
            "name": "NQ + Trend (EMA 50)",
            "asset": "NQ", "tf": 2, "data": (es_2m, nq_2m),
            "cfg": BacktestConfig(fib_entry=0.618, use_trend_filter=True, trend_ema_period=50, breakeven_trigger_r=0.0)
        },
        {
            "name": "NQ + BE + Trend",
            "asset": "NQ", "tf": 2, "data": (es_2m, nq_2m),
            "cfg": BacktestConfig(fib_entry=0.618, use_trend_filter=True, trend_ema_period=50, breakeven_trigger_r=0.5)
        }
    ]

    print("\n" + "="*80)
    print(f"{'TEST NAME':<25} | {'WR':>6} | {'PnL':>10} | {'Trades':>6} | {'MCL':>3}")
    print("-" * 80)

    for test in configs_to_test:
        engine = GoldenProtocolBacktest(test['cfg'])
        # Run
        es_d, nq_d = test['data']
        res = engine.run(es_d, nq_d)
        
        # Filter for asset specific logic (v4.9 Baseline filters)
        trades = []
        blocked = []
        if test['asset'] == 'NQ': blocked = [8, 9, 18, 19]
        
        for t in res.trades:
            if t.asset != test['asset']: continue
            if t.ppi_time and t.ppi_time.hour in blocked: continue
            trades.append(t)
            
        # Calc metrics
        wins = sum(1 for t in trades if t.state == TradeState.WIN)
        losses = sum(1 for t in trades if t.state == TradeState.LOSS)
        count = wins + losses
        pnl = sum(t.pnl for t in trades)
        wr = (wins/count*100) if count > 0 else 0
        
        # MCL
        mcl = cl = 0
        for t in trades:
            if t.state == TradeState.LOSS:
                cl += 1
                mcl = max(mcl, cl)
            elif t.state == TradeState.WIN:
                cl = 0

        print(f"{test['name']:<25} | {wr:>5.1f}% | ${pnl:>9,.0f} | {count:>6} | {mcl:>3}")


if __name__ == "__main__":
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    run_probe(dbn_path)
