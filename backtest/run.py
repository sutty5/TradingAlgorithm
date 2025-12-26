import sys
import os

# Ensure we can import from local backtest dir
sys.path.append(os.path.join(os.getcwd(), 'backtest'))

from loader import load_trades
from engine import TickEngine
from strategy import GoldenProtocol
import datetime

DATA_PATH = r"c:\Users\sutty\TradingStrategyDev\data\databento_trades\trades_es_nq_2025-09-21_2025-12-20.dbn"

def main():
    if not os.path.exists(DATA_PATH):
        print(f"Data file not found: {DATA_PATH}")
        return

    # 1. Init Engine & Strategy
    engine = TickEngine()
    strategy = GoldenProtocol(engine)
    
    # 2. Load Data
    print("Starting Backtest...")
    start_time = datetime.datetime.now()
    
    trade_count = 0
    try:
        for ts, sym, price, size in load_trades(DATA_PATH):
            engine.process_tick(ts, sym, price, size)
            trade_count += 1
            if trade_count % 1_000_000 == 0:
                print(f"Processed {trade_count/1_000_000:.1f}M ticks...", end='\r')
                
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    end_time = datetime.datetime.now()
    print(f"\nBacktest finished in {end_time - start_time}")
    
    # 3. Report
    print("="*40)
    print("RESULTS")
    print("="*40)
    
    total_trades = len(strategy.completed_trades)
    if total_trades == 0:
        print("No trades executed.")
    else:
        wins = [t for t in strategy.completed_trades if t.pnl > 0]
        losses = [t for t in strategy.completed_trades if t.pnl <= 0]
        
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = sum(t.pnl for t in losses)
        net_pnl = gross_profit + gross_loss
        
        win_rate = len(wins) / total_trades * 100
        
        print(f"Total Trades: {total_trades}")
        print(f"Wins: {len(wins)} ({win_rate:.1f}%)")
        print(f"Losses: {len(losses)}")
        print(f"Net PnL (Points): {net_pnl:.2f}")
        print(f"Gross Profit: {gross_profit:.2f}")
        print(f"Gross Loss: {gross_loss:.2f}")
        
    print("="*40)
    # Detailed log
    # for t in strategy.completed_trades:
    #    print(f"{t.symbol} {t.direction} Result: {t.result} PnL: {t.pnl:.2f}")

if __name__ == "__main__":
    main()
