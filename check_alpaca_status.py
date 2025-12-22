
import os
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus

# Load environment variables
load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
PAPER = True

if not API_KEY or not SECRET_KEY:
    print("Error: ALPACA_API_KEY or ALPACA_SECRET_KEY not found in .env")
    sys.exit(1)

def print_separator(title):
    print(f"\n{'='*10} {title} {'='*10}")

def check_status():
    try:
        trading_client = TradingClient(API_KEY, SECRET_KEY, paper=PAPER)
        
        # 1. Account Info
        account = trading_client.get_account()
        print_separator("ACCOUNT STATUS")
        print(f"Status:       {account.status}")
        print(f"Equity:       ${float(account.equity):,.2f}")
        print(f"Cash:         ${float(account.cash):,.2f}")
        print(f"Buying Power: ${float(account.buying_power):,.2f}")
        print(f"Day Trades:   {account.daytrade_count}")
        
        # Calculate Day's PnL (Approximate if equity changed)
        # Note: Last equity is previous close.
        last_equity = float(account.last_equity)
        current_equity = float(account.equity)
        pnl = current_equity - last_equity
        pnl_pct = (pnl / last_equity) * 100 if last_equity > 0 else 0
        
        print(f"Day's PnL:    ${pnl:,.2f} ({pnl_pct:+.2f}%)")

        # 2. Positions
        positions = trading_client.get_all_positions()
        print_separator(f"OPEN POSITIONS ({len(positions)})")
        
        if not positions:
            print("No open positions.")
        else:
            for p in positions:
                print(f"{p.side.upper()} {p.qty} {p.symbol} @ ${float(p.avg_entry_price):.2f}")
                print(f"   Current: ${float(p.current_price):.2f} | PnL: ${float(p.unrealized_pl):.2f} ({float(p.unrealized_plpc)*100:+.2f}%)")

        # 3. Recent Orders (Last 24h)
        # Get orders from yesterday to now
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=24)
        
        request_params = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            limit=50,
            after=start_time
        )
        
        orders = trading_client.get_orders(filter=request_params)
        print_separator(f"RECENT ORDERS (Last 24h: {len(orders)})")
        
        if not orders:
            print("No orders found in the last 24 hours.")
        else:
            # Sort by created_at desc
            orders.sort(key=lambda x: x.created_at, reverse=True)
            for o in orders:
                status_icon = "✅" if o.status == 'filled' else "❌" if o.status in ('canceled', 'rejected') else "⏳"
                time_str = o.created_at.strftime("%H:%M:%S")
                print(f"[{time_str}] {status_icon} {o.status.upper()}: {o.side.upper()} {o.qty} {o.symbol} @ {o.limit_price if o.limit_price else 'MKT'}")
                if o.status == 'rejected':
                    print(f"   Reason: {o.fail_reason}")

    except Exception as e:
        print(f"Error checking Alpaca status: {e}")

if __name__ == "__main__":
    check_status()
