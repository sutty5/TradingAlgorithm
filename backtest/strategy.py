from typing import List, Optional, Deque, Tuple
from collections import deque
from engine import Candle, TickEngine

# Constants
FIB_ENTRY = 0.5
FIB_STOP = 0.893
FIB_TARGET = 0.1
EXPIRY_CANDLES = 7

class Trade:
    __slots__ = ['entry_price', 'stop_price', 'target_price', 'direction', 'active', 'filled_time', 'exit_time', 'pnl', 'result', 'symbol']
    def __init__(self, symbol, entry, stop, target, direction):
        self.symbol = symbol
        self.entry_price = float(entry)
        self.stop_price = float(stop)
        self.target_price = float(target)
        self.direction = int(direction)
        self.active = False
        self.filled_time = 0
        self.exit_time = 0
        self.pnl = 0.0
        self.result = "PENDING"

class GoldenProtocol:
    def __init__(self, engine: TickEngine):
        self.engine = engine
        self.engine.on_candle_close.append(self.on_candle_close)
        self.engine.on_tick.append(self.on_tick)
        
        self.pending_orders: List[Trade] = []
        self.active_trades: List[Trade] = []
        self.completed_trades: List[Trade] = []
        
        # Internal State
        # Pivots: List of {price, time, type='H'|'L'}
        self.pivots = {"ES": [], "NQ": []}
        self.recent_candles = {"ES": deque(maxlen=20), "NQ": deque(maxlen=20)}
        
        # State Machine Per Symbol
        # state: 'IDLE' | 'SWEEP_DETECTED' | 'BOS_CONFIRMED'
        # context: {sweep_candle_ts, sweep_price, divergence_confirmed, ...}
        self.states = {
            "ES": {'state': 'IDLE', 'data': {}}, 
            "NQ": {'state': 'IDLE', 'data': {}}
        }

    def on_candle_close(self, sym: str, candle: Candle):
        self.recent_candles[sym].append(candle)
        self._detect_pivots(sym)
        self._check_signals(sym, candle)
        self._check_expiry(sym, candle)

    def _check_signals(self, sym: str, candle: Candle):
        st = self.states[sym]
        
        # 1. State: IDLE -> look for SWEEP + DIVERGENCE
        if st['state'] == 'IDLE':
            # Identify if we just swept a pivot
            last_piv_h = self._get_last_pivot(sym, 'H')
            last_piv_l = self._get_last_pivot(sym, 'L')
            
            # CHECK BULLISH SWEEP (Low Sweep)
            # Condition: Low < Pivot Low, but (optionally) close > Pivot Low? 
            # Doc says "Fails to hold". We usually treat "Taking out a Low" as the sweep event.
            if last_piv_l and candle.low < last_piv_l['price']:
                # Potential Sweep. Check SMT with other asset.
                other_sym = "NQ" if sym == "ES" else "ES"
                other_piv_l = self._get_last_pivot(other_sym, 'L')
                
                # SMT: We made Lower Low, Other made Higher Low (didn't break).
                # To check if other broke, we need to see if its current price < its last pivot low.
                # Simplified SMT Check:
                # If Other Sym hasn't broken its last pivot low recently.
                
                start_check_time = last_piv_l['time']
                if self._check_smt_divergence(sym, other_sym, 'L', start_check_time):
                    # Valid Sweep
                    st['state'] = 'SWEEP_DETECTED'
                    st['data'] = {
                        'sweep_ts': candle.ts, 
                        'direction': 1, # Bullish
                        'sweep_price': candle.low, # Anchor
                        'reference_pivot': last_piv_l['price']
                    }
                    print(f"[{sym}] BULLISH SWEEP + SMT at {candle.ts}")
                    return

            # CHECK BEARISH SWEEP (High Sweep)
            if last_piv_h and candle.high > last_piv_h['price']:
                other_sym = "NQ" if sym == "ES" else "ES"
                start_check_time = last_piv_h['time']
                
                if self._check_smt_divergence(sym, other_sym, 'H', start_check_time):
                    st['state'] = 'SWEEP_DETECTED'
                    st['data'] = {
                        'sweep_ts': candle.ts, 
                        'direction': -1, # Bearish
                        'sweep_price': candle.high,
                        'reference_pivot': last_piv_h['price']
                    }
                    print(f"[{sym}] BEARISH SWEEP + SMT at {candle.ts}")
                    return

        # 2. State: SWEEP_DETECTED -> look for BOS
        elif st['state'] == 'SWEEP_DETECTED':
            direction = st['data']['direction']
            
            # BULLISH: We swept Low. Need BOS of recent High (Pivot High).
            if direction == 1:
                # Find recent Pivot High active AFTER the sweep started? 
                # Or simply the most recent Pivot High available.
                # Usually BOS is breaking the sub-structure that led to sweep.
                # Simplified: Break the most recent Pivot High registered relative to the sweep.
                
                target_bos_level = self._get_last_pivot(sym, 'H')
                if target_bos_level and candle.close > target_bos_level['price']:
                    # BOS CONFIRMED
                    self._trigger_entry(sym, st['data'], candle, target_bos_level['price'])
                    st['state'] = 'PENDING_ENTRY'
            
            # BEARISH
            elif direction == -1:
                target_bos_level = self._get_last_pivot(sym, 'L')
                if target_bos_level and candle.close < target_bos_level['price']:
                    # BOS CONFIRMED
                    self._trigger_entry(sym, st['data'], candle, target_bos_level['price'])
                    st['state'] = 'PENDING_ENTRY'

    def _trigger_entry(self, sym, sweep_data, breaking_candle, bos_level):
        direction = sweep_data['direction']
        
        # Impulse Range
        # Bullish: Low (Sweep Point) to High (Breaking Candle High)
        # Bearish: High (Sweep Point) to Low (Breaking Candle Low)
        
        if direction == 1: # Long
            impulse_low = sweep_data['sweep_price']
            impulse_high = breaking_candle.high # Or highest since sweep?
            # Range
            rng = impulse_high - impulse_low
            entry = impulse_low + (rng * FIB_ENTRY) # 50% retrace
            stop = impulse_low + (rng * (1.0 - FIB_STOP)) # Should be logic? 
            # Doc: "0.893 Stop Loss". Usually 0.893 OF THE RETRACEMENT? 
            # Or 0.893 Fib extension?
            # Standard Fib tool: 0 is High, 1 is Low. Retrace to 0.5.
            # Stop at 0.893 (Deep).
            
            # Let's trust standard Fib calc:
            # Low = 0.0, High = 1.0. 
            # Retrace down to 0.5.
            # Stop at 0.0? No, usually break of Low.
            # Doc says "SL = 0.893". This usually means 89.3% retrace.
            
            entry = impulse_low + (rng * 0.5)
            stop = impulse_low + (rng * (1 - 0.893)) # Deep retrace
            target = impulse_low + (rng * (1 + 0.1)) # 10% extension? "0.1 Take Profit"
            # Wait, "0.1 Take Profit". If 0 is Low, 1 is High.
            # usually 0.5 is middle. 0 is start.
            # If standard Drawing: 
            #   Point 1 (Start Impulse), Point 2 (End Impulse).
            #   Retrace 0.5.
            #   Stop 0.893 (Near start).
            #   Target -0.1? Or 0.1?
            #   Doc says 1:1 risk model.
            #   Let's check risk. 
            #   Risk = Entry - Stop. Reward = Target - Entry.
            #   If Entry=0.5, Stop=0.107 (approx 0.1 from 0).
            #   Dist = 0.393.
            #   Target must be 0.5 + 0.393 = 0.893? 
            #   Required clarification. But "TP = 0.1" usually means "Just past the high"?
            #   Strategy says "0.1 Take Profit".
            #   Common: -0.27 or -0.618 extensions.
            #   "0.1" might mean -0.1 (extension beyond high).
            #   Let's assume Target is at 1.1? (110% of move).
            #   Let's assume Target is simply High + (risk amount).
            
            # Recalculating for 1:1 Fixed.
            risk = entry - stop
            target = entry + risk
            
        else: # Short
            impulse_high = sweep_data['sweep_price']
            impulse_low = breaking_candle.low
            rng = impulse_high - impulse_low
            
            entry = impulse_high - (rng * 0.5)
            stop = impulse_high - (rng * (1 - 0.893))
            risk = stop - entry
            target = entry - risk

        t = Trade(sym, entry, stop, target, direction)
        self.pending_orders.append(t)
        print(f"[{sym}] ORDER PLACED: {direction} @ {entry:.2f}, SL {stop:.2f}, TP {target:.2f}")

    def _check_expiry(self, sym, candle):
        st = self.states[sym]
        if st['state'] in ['SWEEP_DETECTED', 'PENDING_ENTRY']:
            # Count bars since sweep
            # We stored sweep_ts.
            # Approximation: (current_ts - sweep_ts) / 5min
            elapsed_ns = candle.ts - st['data']['sweep_ts']
            candles_passed = elapsed_ns // 300_000_000_000
            
            if candles_passed > EXPIRY_CANDLES:
                print(f"[{sym}] EXPIRED (Title: {candles_passed} bars)")
                st['state'] = 'IDLE' # Reset
                # Cancel pending orders
                self.pending_orders = [t for t in self.pending_orders if t.symbol != sym]

    def _get_last_pivot(self, sym, ptype):
        # Return last pivot of type H or L
        for p in reversed(self.pivots[sym]):
            if p['type'] == ptype:
                return p
        return None

    def _check_smt_divergence(self, sym, other_sym, check_type, time_limit):
        # Simple SMT:
        # If sym made a new extreme (which triggered this check), 
        # did other_sym ALSO make a new extreme after 'time_limit'?
        # If other_sym did NOT, then divergence exists.
        
        # This requires tracking "Highest High since time X" for both.
        # But we only have pivots.
        # Let's simply check if other_sym has a pivot BEYOND its previous reference pivot?
        # Actually, "Divergence is context".
        # Let's assume Divergence is:
        #   Sym broke pivot.
        #   Other_sym did NOT break its corresponding pivot (last pivot of same type).
        
        # Get last pivot of other_sym
        last_other_piv = self._get_last_pivot(other_sym, check_type)
        if not last_other_piv: return False # Can't compare
        
        # Check current price of other_sym vs its pivot
        # We need "current price" or "recent candle extremes".
        # Using SMT usually means looking at the specific swing.
        # If Sym Broke High, Other Sym should have Broken High.
        # If Other Sym High < Other Pivot High, then SMT.
        
        curr_other_candle = self.recent_candles[other_sym][-1] if self.recent_candles[other_sym] else None
        if not curr_other_candle: return False
        
        if check_type == 'L': # Bullish Div Check
            # Sym made Lower Low (sweep).
            # Other Sym should NOT have made Lower Low.
            # Check most recent candles of Other Sym to see if they broke `last_other_piv`
            
            # Rigorous: Look at "Lowest Low of Other Sym since time_limit".
            # time_limit here is the time of the Pivot we just broke.
            # So, in the same timeframe, did Other Sym break its pivot?
            
            # Simplification: Just look at recent few candles.
            if curr_other_candle.low > last_other_piv['price']:
                return True
                
        elif check_type == 'H': # Bearish Div Check
            # Sym made Higher High.
            # Other Sym should NOT have made Higher High.
            if curr_other_candle.high < last_other_piv['price']:
                return True
                
        return False

    def on_tick(self, ts: int, sym: str, price: float):
        # Entry Fills
        for trade in self.pending_orders:
            if trade.symbol != sym: continue
            if trade.active: continue
            
            if trade.direction == 1: # Long
                if price <= trade.entry_price:
                    trade.active = True
                    trade.filled_time = ts
                    self.active_trades.append(trade)
                    self.pending_orders.remove(trade)
                    print(f"FILLED LONG {sym} @ {price}")
                    break 
            elif trade.direction == -1: # Short
                if price >= trade.entry_price:
                    trade.active = True
                    trade.filled_time = ts
                    self.active_trades.append(trade)
                    self.pending_orders.remove(trade)
                    print(f"FILLED SHORT {sym} @ {price}")
                    break
        
        # Exit Fills (First Touch)
        for trade in list(self.active_trades):
            if trade.symbol != sym: continue
            
            if trade.direction == 1:
                # Check Stop
                if price <= trade.stop_price:
                    self._close_trade(trade, ts, 'SL', trade.stop_price)
                # Check Target
                elif price >= trade.target_price:
                    self._close_trade(trade, ts, 'TP', trade.target_price)
            else:
                if price >= trade.stop_price:
                    self._close_trade(trade, ts, 'SL', trade.stop_price)
                elif price <= trade.target_price:
                    self._close_trade(trade, ts, 'TP', trade.target_price)

    def _detect_pivots(self, sym: str):
        hist = self.recent_candles[sym]
        if len(hist) < 3: return
        
        left = hist[-3]
        mid = hist[-2]
        right = hist[-1]
        
        if left.high < mid.high and right.high < mid.high:
            self.pivots[sym].append( {'type': 'H', 'price': mid.high, 'time': mid.ts} )
        if left.low > mid.low and right.low > mid.low:
            self.pivots[sym].append( {'type': 'L', 'price': mid.low, 'time': mid.ts} )

    def _close_trade(self, trade, ts, reason, price):
        trade.result = reason
        trade.exit_time = ts
        trade.pnl = (price - trade.entry_price) * trade.direction
        self.active_trades.remove(trade)
        self.completed_trades.append(trade)
        print(f"CLOSED {str(trade.direction).replace('1','LONG')} {trade.symbol}: {reason} PnL: {trade.pnl:.2f}")


