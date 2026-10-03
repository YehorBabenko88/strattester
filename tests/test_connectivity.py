from strattester.connectivity import check_bybit,check_telegram

class R:
    status_code=200
    def raise_for_status(self): pass
    def json(self): return {'ok':True,'result':{'id':1}}

class Session:
    def get(self,*a,**k): return R()

class Bybit:
    def fetch_linear_instruments(self): return [{'symbol':'BTCUSDT'}]

def test_connectivity_checks_are_read_only():
    b=check_bybit(Bybit())
    t=check_telegram('secret',session=Session())
    assert b.ok and '1 instrument' in b.detail
    assert t.ok and t.detail=='bot authenticated'
