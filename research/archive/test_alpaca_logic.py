
import unittest
from datetime import datetime
from alpaca_paper_trader import GoldenProtocolLive, Candle, TradeState, SYMBOL_NQ, SYMBOL_ES

class TestAlpacaLogic(unittest.TestCase):
    def setUp(self):
        self.logic = GoldenProtocolLive()
        
    def create_candle(self, symbol, close, open_p, high, low):
        return Candle(
            timestamp=datetime(2025, 12, 22, 10, 0), # 10 AM (Not blocked)
            symbol=symbol,
            open=open_p,
            close=close,
            high=high,
            low=low,
            volume=1000
        )

    def test_ppi_detection(self):
        """Test if PPI is detected when directions diverge."""
        # NQ Green (+1), ES Red (-1) -> Divergence
        nq = self.create_candle(SYMBOL_NQ, 101, 100, 102, 99)
        es = self.create_candle(SYMBOL_ES, 199, 200, 201, 198)
        
        self.logic.on_candle_close(nq, es)
        self.assertEqual(self.logic.state, TradeState.PPI)
        self.assertEqual(self.logic.setup['ppi_nq_dir'], 1)

    def test_short_sweep_trigger(self):
        """Test if Short Sweep triggers after PPI."""
        # 1. Trigger PPI (Bearish setup? NQ Green, ES Red)
        nq = self.create_candle(SYMBOL_NQ, 101, 100, 102, 99)
        es = self.create_candle(SYMBOL_ES, 199, 200, 201, 198)
        self.logic.on_candle_close(nq, es)
        
        # 2. Sweep Candle: High > PPI High (102), Close <= PPI High
        # Let's say High 103, Close 101
        nq_sweep = self.create_candle(SYMBOL_NQ, 101, 100, 103, 100)
        es_sweep = self.create_candle(SYMBOL_ES, 199, 200, 200, 198) # ES doesn't matter for sweep
        
        self.logic.on_candle_close(nq_sweep, es_sweep)
        self.assertEqual(self.logic.state, TradeState.SWEEP)
        self.assertEqual(self.logic.setup['sweep_type'], 'SHORT')
        self.assertEqual(self.logic.setup['sweep_extreme'], 103)

    def test_bos_and_signal(self):
        """Test if BOS fires a signal with correct Bracket prices."""
        # 1. PPI
        nq = self.create_candle(SYMBOL_NQ, 100, 99, 100, 99) # Doji/small. 
        # Wait, direction needs to be non-zero.
        nq = self.create_candle(SYMBOL_NQ, 101, 100, 102, 99) # +1
        es = self.create_candle(SYMBOL_ES, 199, 200, 201, 198) # -1
        self.logic.on_candle_close(nq, es)
        
        # 2. Sweep (Short)
        # PPI High = 102.
        nq_sweep = self.create_candle(SYMBOL_NQ, 101, 100, 103, 99) # High 103 > 102
        self.logic.on_candle_close(nq_sweep, es)
        
        # 3. BOS
        # PPI Low = 99.
        # Close < 99.
        nq_bos = self.create_candle(SYMBOL_NQ, 98, 99, 100, 97)
        signal = self.logic.on_candle_close(nq_bos, es)
        
        self.assertEqual(self.logic.state, TradeState.FILLED)
        self.assertIsNotNone(signal)
        
        # Verify Levels
        # Sweep High (Fib 1) = 103 (Stop)
        # BOS Low (Fib 0) = 97 (Target)
        # Range = 6
        # Entry = 97 + (6 * 0.618) = 97 + 3.708 = 100.708 -> Round 100.71
        
        self.assertEqual(signal['entry'], 100.71)
        self.assertEqual(signal['stop'], 103.0)
        self.assertEqual(signal['target'], 97.0)

if __name__ == '__main__':
    unittest.main()
