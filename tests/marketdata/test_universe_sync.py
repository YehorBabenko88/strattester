import pytest
from strattester.marketdata.bybit_client import BybitClient
from strattester.marketdata.instruments import InstrumentRegistry,InstrumentStatus
from strattester.marketdata.universe_sync import UniverseSynchronizer
from strattester.marketdata.sqlite_store import SQLiteMarketStore
from strattester.marketdata.sync_engine import SyncEngine,DataRequirement,SyncState

class PayloadResponse:
    status_code=200
    def __init__(self,payload): self.payload=payload
    def json(self): return self.payload
class PayloadSession:
    def __init__(self,payload): self.payload=payload
    def get(self,*a,**k): return PayloadResponse(self.payload)

def test_bybit_discovers_only_trading_usdt_linear_perpetuals():
    payload={'retCode':0,'result':{'list':[
      {'symbol':'BTCUSDT','status':'Trading','quoteCoin':'USDT','contractType':'LinearPerpetual'},
      {'symbol':'OLDUSDT','status':'Settled','quoteCoin':'USDT','contractType':'LinearPerpetual'},
      {'symbol':'BTCUSDC','status':'Trading','quoteCoin':'USDC','contractType':'LinearPerpetual'}]}}
    c=BybitClient(session=PayloadSession(payload))
    assert c.fetch_linear_symbols()=={'BTCUSDT'}

def test_universe_sync_retains_disappeared_instrument(tmp_path):
    class C:
        def __init__(self): self.symbols={'AUSDT','BUSDT'}
        def fetch_linear_symbols(self): return set(self.symbols)
    c=C(); reg=InstrumentRegistry.open(tmp_path/'i.db'); u=UniverseSynchronizer(reg,c)
    u.sync(1000); c.symbols={'BUSDT'}; u.sync(2000)
    assert reg.get('AUSDT').status is InstrumentStatus.MISSING
    u.sync(3000)
    assert reg.get('AUSDT').status is InstrumentStatus.DELISTED
    assert reg.eligible_at('AUSDT',1500)
    reg.close()

def test_empty_exchange_snapshot_does_not_mass_delist(tmp_path):
    from strattester.marketdata.universe_sync import UniverseSnapshotError
    class C:
        def __init__(self): self.symbols={'AUSDT','BUSDT'}
        def fetch_linear_symbols(self): return set(self.symbols)
    c=C(); reg=InstrumentRegistry.open(tmp_path/'i.db'); u=UniverseSynchronizer(reg,c)
    u.sync(1000); c.symbols=set()
    try:
        u.sync(2000)
        assert False, 'expected suspicious snapshot rejection'
    except UniverseSnapshotError:
        pass
    assert reg.active_symbols()=={'AUSDT','BUSDT'}
    reg.close()

def test_reverse_chronological_pages_do_not_skip_middle(tmp_path):
    def row(t): return [str(t),'1','1.1','.9','1','10','100']
    class ReversePaged:
        def __init__(self): self.calls=[]
        def fetch_klines(self,symbol,start,end,interval='1',limit=1000):
            self.calls.append((start,end))
            all_rows=[row(0),row(60000),row(120000),row(180000),row(240000)]
            eligible=[r for r in all_rows if start<=int(r[0])<=end]
            return list(reversed(eligible))[:2]
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    r=SyncEngine(s,ReversePaged(),clock_ms=lambda:999999).sync_requirement(DataRequirement('BTCUSDT',start_ms=0,end_ms=240000))
    assert r.state is SyncState.READY
    assert s.coverage('BTCUSDT').count==5
    s.close()


def test_large_nonempty_shrink_is_rejected_before_reconcile(tmp_path):
    from strattester.marketdata.universe_sync import UniverseSnapshotError

    class C:
        def __init__(self, symbols):
            self.symbols = set(symbols)

        def fetch_linear_symbols(self):
            return set(self.symbols)

    original = {f"S{i:03d}USDT" for i in range(100)}

    c = C(original)
    reg = InstrumentRegistry.open(tmp_path / "i.db")
    u = UniverseSynchronizer(reg, c)

    u.sync(1000)

    # 60/100 passes the historical 0.5 size-ratio guard, but losing
    # 40% of the active universe in one response is unsafe lifecycle
    # evidence and must not reach reconcile().
    c.symbols = set(sorted(original)[:60])

    try:
        u.sync(2000)
        assert False, "expected mass-disappearance rejection"
    except UniverseSnapshotError:
        pass

    assert reg.active_symbols() == original

    for symbol in original:
        assert reg.get(symbol).status is InstrumentStatus.ACTIVE
        assert reg.intervals(symbol) == [(1000, None)]

    reg.close()


def test_small_universe_shrink_still_uses_normal_missing_confirmation(tmp_path):
    class C:
        def __init__(self, symbols):
            self.symbols = set(symbols)

        def fetch_linear_symbols(self):
            return set(self.symbols)

    original = {f"S{i:03d}USDT" for i in range(100)}
    removed = set(sorted(original)[-5:])

    c = C(original)
    reg = InstrumentRegistry.open(tmp_path / "i.db")
    u = UniverseSynchronizer(reg, c)

    u.sync(1000)

    c.symbols = original - removed

    u.sync(2000)

    assert all(
        reg.get(symbol).status is InstrumentStatus.MISSING
        for symbol in removed
    )

    u.sync(3000)

    assert all(
        reg.get(symbol).status is InstrumentStatus.DELISTED
        for symbol in removed
    )

    assert reg.active_symbols() == original - removed

    reg.close()

class LifecycleClient:
    def __init__(self, snapshots=None, fail_status=None):
        self.snapshots = snapshots or {}
        self.fail_status = fail_status
        self.calls = []

    def fetch_linear_instruments(self, status=None):
        self.calls.append(status)

        if status == self.fail_status:
            raise RuntimeError(
                f"simulated {status} fetch failure"
            )

        return [
            dict(row)
            for row in self.snapshots.get(status, ())
        ]


def _instrument(symbol, status, delivery_time=None):
    row = {
        'symbol': symbol,
        'status': status,
        'quoteCoin': 'USDT',
        'contractType': 'LinearPerpetual',
    }

    if delivery_time is not None:
        row['deliveryTime'] = str(delivery_time)

    return row


def test_multistatus_failure_before_closed_page_cannot_mutate_registry(
    tmp_path,
):
    reg=InstrumentRegistry.open(tmp_path/'i.db')
    reg.reconcile({'AUSDT','BUSDT'},1000)

    before_a=reg.get('AUSDT')
    before_b=reg.get('BUSDT')
    before_a_intervals=reg.intervals('AUSDT')
    before_b_intervals=reg.intervals('BUSDT')

    c=LifecycleClient(
        snapshots={
            'Trading':[
                _instrument(
                    'BUSDT',
                    'Trading',
                ),
            ],
            'PreLaunch':[
                _instrument(
                    'NEWUSDT',
                    'PreLaunch',
                ),
            ],
        },
        fail_status='Closed',
    )

    u=UniverseSynchronizer(reg,c)

    try:
        u.sync(2000)
        assert False, 'expected simulated fetch failure'
    except RuntimeError as exc:
        assert 'Closed' in str(exc)

    # Trading/PreLaunch data was already fetched, but because Closed failed
    # the entire exchange observation is discarded.
    assert reg.get('AUSDT')==before_a
    assert reg.get('BUSDT')==before_b
    assert reg.get('NEWUSDT') is None
    assert reg.intervals('AUSDT')==before_a_intervals
    assert reg.intervals('BUSDT')==before_b_intervals

    assert c.calls==[
        'Trading',
        'PendingOpen',
        'PreLaunch',
        'Delivering',
        'Closed',
    ]

    reg.close()


def test_prelaunch_then_trading_through_universe_sync(tmp_path):
    reg=InstrumentRegistry.open(tmp_path/'i.db')

    c=LifecycleClient(
        snapshots={
            'PreLaunch':[
                _instrument(
                    'NEWUSDT',
                    'PreLaunch',
                ),
            ],
        }
    )

    u=UniverseSynchronizer(reg,c)

    assert u.sync(1000)==set()

    assert (
        reg.get('NEWUSDT').status
        is InstrumentStatus.PRE_LISTING
    )
    assert reg.intervals('NEWUSDT')==[]

    c.snapshots={
        'Trading':[
            _instrument(
                'NEWUSDT',
                'Trading',
            ),
        ],
    }

    assert u.sync(2000)=={'NEWUSDT'}

    assert (
        reg.get('NEWUSDT').status
        is InstrumentStatus.ACTIVE
    )
    assert reg.intervals('NEWUSDT')==[
        (2000,None),
    ]

    reg.close()


def test_pending_open_never_traded_is_not_backtest_eligible(tmp_path):
    reg=InstrumentRegistry.open(tmp_path/'i.db')

    c=LifecycleClient(
        snapshots={
            'PendingOpen':[
                _instrument(
                    'WAITUSDT',
                    'PendingOpen',
                ),
            ],
        }
    )

    UniverseSynchronizer(reg,c).sync(1000)

    assert (
        reg.get('WAITUSDT').status
        is InstrumentStatus.PRE_LISTING
    )
    assert reg.intervals('WAITUSDT')==[]
    assert not reg.eligible_at('WAITUSDT',1000)

    reg.close()


def test_delivering_known_active_becomes_suspended_not_delisted(
    tmp_path,
):
    reg=InstrumentRegistry.open(tmp_path/'i.db')
    reg.reconcile({'XUSDT'},1000)

    c=LifecycleClient(
        snapshots={
            'Delivering':[
                _instrument(
                    'XUSDT',
                    'Delivering',
                ),
            ],
        }
    )

    UniverseSynchronizer(reg,c).sync(2000)

    assert (
        reg.get('XUSDT').status
        is InstrumentStatus.SUSPENDED
    )
    assert reg.get('XUSDT').delisted_at is None
    assert reg.intervals('XUSDT')==[
        (1000,2000),
    ]

    reg.close()


def test_closed_after_offline_reboot_uses_exchange_delivery_time(
    tmp_path,
):
    p=tmp_path/'i.db'

    reg=InstrumentRegistry.open(p)
    reg.reconcile({'OLDUSDT'},1000)
    reg.close()

    # PC returns at 5000. Bybit says the actual perpetual delisting was
    # 3000.
    reg=InstrumentRegistry.open(p)

    c=LifecycleClient(
        snapshots={
            'Closed':[
                _instrument(
                    'OLDUSDT',
                    'Closed',
                    delivery_time=3000,
                ),
            ],
        }
    )

    UniverseSynchronizer(reg,c).sync(5000)

    rec=reg.get('OLDUSDT')

    assert rec.status is InstrumentStatus.DELISTED
    assert rec.delisted_at==3000
    assert rec.last_seen==5000
    assert reg.intervals('OLDUSDT')==[
        (1000,3000),
    ]
    assert reg.eligible_at('OLDUSDT',2999)
    assert not reg.eligible_at('OLDUSDT',3000)

    reg.close()

    # Persistence check after another reboot.
    reg=InstrumentRegistry.open(p)

    assert (
        reg.get('OLDUSDT').status
        is InstrumentStatus.DELISTED
    )
    assert reg.get('OLDUSDT').delisted_at==3000
    assert reg.intervals('OLDUSDT')==[
        (1000,3000),
    ]

    reg.close()


def test_explicit_closed_status_prevents_false_mass_shrink_rejection(
    tmp_path,
):
    original={
        f'S{i:03d}USDT'
        for i in range(100)
    }

    remaining=set(
        sorted(original)[:40]
    )

    closed=original-remaining

    reg=InstrumentRegistry.open(tmp_path/'i.db')
    reg.reconcile(original,1000)

    c=LifecycleClient(
        snapshots={
            'Trading':[
                _instrument(
                    symbol,
                    'Trading',
                )
                for symbol in sorted(remaining)
            ],
            'Closed':[
                _instrument(
                    symbol,
                    'Closed',
                    delivery_time=1500,
                )
                for symbol in sorted(closed)
            ],
        }
    )

    # Trading alone fell 100 -> 40 and would previously be rejected.
    # Explicit Closed evidence accounts for every missing instrument.
    result=UniverseSynchronizer(reg,c).sync(2000)

    assert result==remaining
    assert reg.active_symbols()==remaining

    assert all(
        reg.get(symbol).status
        is InstrumentStatus.DELISTED
        for symbol in closed
    )

    assert all(
        reg.get(symbol).delisted_at==1500
        for symbol in closed
    )

    reg.close()


def test_unexplained_mass_shrink_still_fails_with_multistatus_client(
    tmp_path,
):
    original={
        f'S{i:03d}USDT'
        for i in range(100)
    }

    remaining=set(
        sorted(original)[:40]
    )

    reg=InstrumentRegistry.open(tmp_path/'i.db')
    reg.reconcile(original,1000)

    c=LifecycleClient(
        snapshots={
            'Trading':[
                _instrument(
                    symbol,
                    'Trading',
                )
                for symbol in sorted(remaining)
            ],
        }
    )

    from strattester.marketdata.universe_sync import (
        UniverseSnapshotError,
    )

    with pytest.raises(
        UniverseSnapshotError,
        match='shrank suspiciously|lost too many',
    ):
        UniverseSynchronizer(reg,c).sync(2000)

    # No missing confirmation or interval mutation was consumed.
    assert reg.active_symbols()==original

    assert all(
        reg.intervals(symbol)==[(1000,None)]
        for symbol in original
    )

    reg.close()


def test_cross_status_overlap_fails_before_registry_mutation(tmp_path):
    reg=InstrumentRegistry.open(tmp_path/'i.db')
    reg.reconcile({'XUSDT'},1000)

    c=LifecycleClient(
        snapshots={
            'Trading':[
                _instrument(
                    'XUSDT',
                    'Trading',
                ),
            ],
            'Closed':[
                _instrument(
                    'XUSDT',
                    'Closed',
                    delivery_time=900,
                ),
            ],
        }
    )

    from strattester.marketdata.universe_sync import (
        UniverseSnapshotError,
    )

    with pytest.raises(
        UniverseSnapshotError,
        match='multiple status snapshots',
    ):
        UniverseSynchronizer(reg,c).sync(2000)

    assert (
        reg.get('XUSDT').status
        is InstrumentStatus.ACTIVE
    )
    assert reg.intervals('XUSDT')==[
        (1000,None),
    ]

    reg.close()


def test_unknown_closed_history_does_not_flood_fresh_registry(tmp_path):
    reg=InstrumentRegistry.open(tmp_path/'i.db')

    c=LifecycleClient(
        snapshots={
            'Trading':[
                _instrument(
                    'BTCUSDT',
                    'Trading',
                ),
            ],
            'Closed':[
                _instrument(
                    f'OLD{i:03d}USDT',
                    'Closed',
                    delivery_time=500,
                )
                for i in range(100)
            ],
        }
    )

    UniverseSynchronizer(reg,c).sync(1000)

    assert reg.get('BTCUSDT') is not None

    assert all(
        reg.get(f'OLD{i:03d}USDT') is None
        for i in range(100)
    )

    reg.close()
