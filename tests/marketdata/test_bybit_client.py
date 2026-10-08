import pytest
from strattester.marketdata.bybit_client import BybitClient,RetryPolicy,BybitAccessError,RetryableBybitError,BybitResponseError

class Response:
    def __init__(self,status,payload=None,headers=None): self.status_code=status; self.payload=payload or {'retCode':0,'result':{}};self.headers=headers or {}
    def json(self): return self.payload
class Session:
    def __init__(self,statuses): self.statuses=list(statuses); self.calls=0
    def get(self,*a,**k): self.calls+=1; return Response(self.statuses.pop(0))

def test_403_fails_without_retry():
    s=Session([403]); c=BybitClient(session=s,sleep=lambda _:None)
    with pytest.raises(BybitAccessError): c.get('/x')
    assert s.calls==1

def test_429_retries_then_succeeds():
    s=Session([429,200]); sleeps=[]
    c=BybitClient(session=s,sleep=sleeps.append,retry=RetryPolicy(attempts=3,base_delay=.1))
    assert c.get('/x')['retCode']==0
    assert s.calls==2 and sleeps==[.1]

def test_5xx_exhaustion_is_retryable():
    s=Session([500,503])
    c=BybitClient(session=s,sleep=lambda _:None,retry=RetryPolicy(attempts=2))
    with pytest.raises(RetryableBybitError): c.get('/x')


def test_retry_after_is_honored_but_bounded():
    class S:
        calls=0
        def get(self,*a,**k):
            self.calls+=1
            return Response(429,headers={'Retry-After':'99'}) if self.calls==1 else Response(200)
    s=S();sleeps=[];c=BybitClient(session=s,sleep=sleeps.append,retry=RetryPolicy(2,.1,2))
    c.get('/x');assert sleeps==[2]

def test_bybit_rate_limit_retcode_is_retryable():
    class S:
        calls=0
        def get(self,*a,**k):
            self.calls+=1
            return Response(200,{'retCode':10006,'retMsg':'Too many visits'}) if self.calls==1 else Response(200)
    s=S();c=BybitClient(session=s,sleep=lambda _:None,retry=RetryPolicy(2,0,1))
    assert c.get('/x')['retCode']==0 and s.calls==2

def test_invalid_retry_policy_fails_before_network():
    s=Session([200]);c=BybitClient(session=s,retry=RetryPolicy(0,1,1))
    with pytest.raises(ValueError):c.get('/x')
    assert s.calls==0

def _linear_row(symbol, status='Trading'):
    return {
        'symbol': symbol,
        'status': status,
        'quoteCoin': 'USDT',
        'contractType': 'LinearPerpetual',
    }


def test_instrument_pagination_two_pages():
    class C(BybitClient):
        def __init__(self):
            self.calls = []

        def get(self, path, params=None):
            self.calls.append((path, dict(params or {})))

            if len(self.calls) == 1:
                return {
                    'retCode': 0,
                    'result': {
                        'list': [_linear_row('AAAUSDT')],
                        'nextPageCursor': 'PAGE2',
                    },
                }

            if len(self.calls) == 2:
                return {
                    'retCode': 0,
                    'result': {
                        'list': [_linear_row('BBBUSDT')],
                        'nextPageCursor': '',
                    },
                }

            raise AssertionError('unexpected third request')

    c = C()

    rows = c.fetch_linear_instruments()

    assert {row['symbol'] for row in rows} == {
        'AAAUSDT',
        'BBBUSDT',
    }
    assert len(c.calls) == 2
    assert 'cursor' not in c.calls[0][1]
    assert c.calls[1][1]['cursor'] == 'PAGE2'


def test_repeated_pagination_cursor_fails_closed_without_loop():
    class C(BybitClient):
        def __init__(self):
            self.calls = 0

        def get(self, path, params=None):
            self.calls += 1

            if self.calls > 2:
                raise AssertionError(
                    'pagination loop made an unexpected third request'
                )

            return {
                'retCode': 0,
                'result': {
                    'list': [_linear_row(f'S{self.calls}USDT')],
                    'nextPageCursor': 'SAME',
                },
            }

    c = C()

    with pytest.raises(
        BybitResponseError,
        match='repeated cursor',
    ):
        c.fetch_linear_instruments()

    assert c.calls == 2


@pytest.mark.parametrize(
    'payload',
    [
        {'retCode': 0},
        {'retCode': 0, 'result': None},
        {'retCode': 0, 'result': {}},
        {'retCode': 0, 'result': {'list': None}},
        {'retCode': 0, 'result': {'list': {}}},
    ],
)
def test_malformed_instrument_page_fails_closed(payload):
    class C(BybitClient):
        def get(self, path, params=None):
            return payload

    with pytest.raises(BybitResponseError):
        C().fetch_linear_instruments()


def test_invalid_pagination_cursor_type_fails_closed():
    class C(BybitClient):
        def get(self, path, params=None):
            return {
                'retCode': 0,
                'result': {
                    'list': [_linear_row('AAAUSDT')],
                    'nextPageCursor': 123,
                },
            }

    with pytest.raises(
        BybitResponseError,
        match='invalid nextPageCursor',
    ):
        C().fetch_linear_instruments()


def test_invalid_instrument_row_fails_closed():
    class C(BybitClient):
        def get(self, path, params=None):
            return {
                'retCode': 0,
                'result': {
                    'list': [None],
                    'nextPageCursor': '',
                },
            }

    with pytest.raises(
        BybitResponseError,
        match='invalid row',
    ):
        C().fetch_linear_instruments()


def test_second_page_failure_never_returns_partial_universe():
    class C(BybitClient):
        def __init__(self):
            self.calls = 0

        def get(self, path, params=None):
            self.calls += 1

            if self.calls == 1:
                return {
                    'retCode': 0,
                    'result': {
                        'list': [_linear_row('AAAUSDT')],
                        'nextPageCursor': 'PAGE2',
                    },
                }

            raise RetryableBybitError('second page unavailable')

    c = C()

    with pytest.raises(
        RetryableBybitError,
        match='second page unavailable',
    ):
        c.fetch_linear_instruments()

    assert c.calls == 2


def test_non_trading_and_non_linear_rows_are_filtered():
    class C(BybitClient):
        def get(self, path, params=None):
            return {
                'retCode': 0,
                'result': {
                    'list': [
                        _linear_row('ACTIVEUSDT'),
                        _linear_row('SETTLEDUSDT', status='Settled'),
                        {
                            'symbol': 'WRONGQUOTE',
                            'status': 'Trading',
                            'quoteCoin': 'USDC',
                            'contractType': 'LinearPerpetual',
                        },
                        {
                            'symbol': 'WRONGTYPE',
                            'status': 'Trading',
                            'quoteCoin': 'USDT',
                            'contractType': 'InversePerpetual',
                        },
                    ],
                    'nextPageCursor': '',
                },
            }

    rows = C().fetch_linear_instruments()

    assert [row['symbol'] for row in rows] == ['ACTIVEUSDT']
def test_explicit_instrument_status_is_sent_and_returned():
    class C(BybitClient):
        def __init__(self):
            self.params = None

        def get(self, path, params=None):
            self.params = dict(params or {})
            return {
                'retCode': 0,
                'result': {
                    'list': [
                        _linear_row(
                            'OLDUSDT',
                            status='Closed',
                        ),
                        _linear_row(
                            'LIVEUSDT',
                            status='Trading',
                        ),
                    ],
                    'nextPageCursor': '',
                },
            }

    c = C()

    rows = c.fetch_linear_instruments(status='Closed')

    assert c.params['status'] == 'Closed'
    assert [x['symbol'] for x in rows] == ['OLDUSDT']


def test_explicit_status_is_preserved_across_pagination():
    class C(BybitClient):
        def __init__(self):
            self.calls = []

        def get(self, path, params=None):
            params = dict(params or {})
            self.calls.append(params)

            if len(self.calls) == 1:
                return {
                    'retCode': 0,
                    'result': {
                        'list': [
                            _linear_row(
                                'AUSDT',
                                status='PreLaunch',
                            ),
                        ],
                        'nextPageCursor': 'NEXT',
                    },
                }

            return {
                'retCode': 0,
                'result': {
                    'list': [
                        _linear_row(
                            'BUSDT',
                            status='PreLaunch',
                        ),
                    ],
                    'nextPageCursor': '',
                },
            }

    c = C()

    rows = c.fetch_linear_instruments(
        status='PreLaunch',
    )

    assert [x['symbol'] for x in rows] == [
        'AUSDT',
        'BUSDT',
    ]

    assert len(c.calls) == 2
    assert c.calls[0]['status'] == 'PreLaunch'
    assert c.calls[1]['status'] == 'PreLaunch'
    assert c.calls[1]['cursor'] == 'NEXT'


@pytest.mark.parametrize(
    'status',
    [
        '',
        '   ',
        123,
    ],
)
def test_invalid_explicit_instrument_status_is_rejected(status):
    class C(BybitClient):
        def __init__(self):
            self.calls = 0

        def get(self, path, params=None):
            self.calls += 1
            raise AssertionError(
                'network must not be reached'
            )

    c = C()

    with pytest.raises(ValueError):
        c.fetch_linear_instruments(status=status)

    assert c.calls == 0


def test_default_instrument_query_remains_trading_only():
    class C(BybitClient):
        def __init__(self):
            self.params = None

        def get(self, path, params=None):
            self.params = dict(params or {})

            return {
                'retCode': 0,
                'result': {
                    'list': [
                        _linear_row(
                            'LIVEUSDT',
                            status='Trading',
                        ),
                        _linear_row(
                            'PENDINGUSDT',
                            status='PendingOpen',
                        ),
                        _linear_row(
                            'PREUSDT',
                            status='PreLaunch',
                        ),
                        _linear_row(
                            'OLDUSDT',
                            status='Closed',
                        ),
                    ],
                    'nextPageCursor': '',
                },
            }

    c = C()

    rows = c.fetch_linear_instruments()

    assert 'status' not in c.params
    assert [x['symbol'] for x in rows] == [
        'LIVEUSDT',
    ]


def test_current_funding_intervals_are_not_historical_schedules():
    class C(BybitClient):
        def fetch_linear_instruments(self):
            return [
                {**_linear_row('BTCUSDT'), 'fundingInterval': 480},
                {**_linear_row('ETHUSDT'), 'fundingInterval': '60'},
            ]
    assert C().fetch_current_funding_intervals() == {
        'BTCUSDT': 28_800_000,
        'ETHUSDT': 3_600_000,
    }


@pytest.mark.parametrize('invalid', [None, 0, -1, True, 'x', '1.5', ' 60 ', '60 ', '060', '6e1', 60.0])
def test_invalid_current_funding_metadata_fails_closed(invalid):
    class C(BybitClient):
        def fetch_linear_instruments(self):
            return [{**_linear_row('BTCUSDT'), 'fundingInterval': invalid}]
    with pytest.raises(BybitResponseError):
        C().fetch_current_funding_intervals()


def test_duplicate_current_funding_metadata_fails_closed():
    class C(BybitClient):
        def fetch_linear_instruments(self):
            return [
                {**_linear_row('BTCUSDT'), 'fundingInterval': 480},
                {**_linear_row('BTCUSDT'), 'fundingInterval': 60},
            ]
    with pytest.raises(BybitResponseError, match='duplicate'):
        C().fetch_current_funding_intervals()
