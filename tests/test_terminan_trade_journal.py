import sqlite3
import tempfile
import unittest
from pathlib import Path
from strattester.terminan_trade_journal import append_trades,read_trades

class JournalTests(unittest.TestCase):
    def test_round_trip_and_idempotence(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'research.sqlite';con=sqlite3.connect(p)
            trades=[dict(entry_time=1000,exit_time=2000,entry_price=100,exit_price=110,side='long',quantity=2,net_pnl=20,fees=0,metadata={})]
            append_trades(con,'run','BTCUSDT','strategy',trades)
            append_trades(con,'run','BTCUSDT','strategy',trades)
            con.close()
            result=read_trades(p,'run','BTCUSDT')
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['entry_ms'],1000)
    def test_missing_quantity_is_rejected(self):
        with sqlite3.connect(':memory:') as con:
            with self.assertRaises(ValueError):
                append_trades(con,'r','BTCUSDT','s',[dict(entry_time=1,exit_time=2,entry_price=1,exit_price=2,side='long')])
if __name__=='__main__':unittest.main()
