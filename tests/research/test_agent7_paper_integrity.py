"""Independent SYNTHETIC accounting and actual child-process loss, node-local only."""
import copy
from contextlib import closing
from decimal import Decimal
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

import pytest
from strattester.research.quote_paper import PaperLedger, canonical, digest, evaluate

SYMBOLS = ('BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT',
           'DOGEUSDT','ADAUSDT','AVAXUSDT','LINKUSDT','DOTUSDT')


def request(symbol='ETHUSDT', side='long'):
    def receipt(name, **values):
        value = dict(receipt_id=name, symbol=symbol, source_id='SYNTHETIC_AGENT7',
                     raw_sha256='a'*64, **values)
        value['sha256'] = digest(value)
        return value
    return dict(schema='stratt.paper.quote.request.v1', request_id='operation-1',
        strategy='agent7-independent', strategy_revision='b'*40,
        evidence_class='SYNTHETIC', symbol=symbol,
        units={'price':'USDT/'+symbol[:-4], 'qty':symbol[:-4]},
        policy=dict(notional=100., fee_bps=7., slippage_bps=25., latency_ms=10,
                    max_quote_age_ms=1000, max_hold_ms=1000),
        signal=receipt('signal', decision_ms=1000, observed_ms=1000, expires_ms=1500, side=side),
        close_signal=receipt('exit', decision_ms=1200, observed_ms=1200, expires_ms=1500),
        quotes=[receipt('q1', epoch='fixture-epoch', sequence=1, event_ms=1010,
                        observed_ms=1011, bid=99., ask=100.),
                receipt('q2', epoch='fixture-epoch', sequence=2, event_ms=1210,
                        observed_ms=1211, bid=110., ask=111.)],
        funding=receipt('funding', kind='COMPLETE_EVENTS', observed_ms=1200,
                        previous_ms=0, next_ms=2200, interval_ms=1100,
                        events=[receipt('f-event', event_ms=1100, observed_ms=1101,
                                        rate=.002, mark_price=105.)]))


def oracle(side):
    """Decimal oracle uses declared bid/ask directly, not production helpers."""
    d = Decimal
    direction = d(1) if side == 'long' else d(-1)
    raw_entry, raw_exit = (d(100),d(110)) if side == 'long' else (d(99),d(111))
    entry = raw_entry*(1+direction*d('.0025'))
    exit_price = raw_exit*(1-direction*d('.0025'))
    qty = d(100)/entry
    gross_raw = direction*qty*(raw_exit-raw_entry)
    gross_fill = direction*qty*(exit_price-entry)
    fees = qty*(entry+exit_price)*d('.0007')
    funding = direction*qty*d(105)*d('.002')
    return dict(entry_price=entry, exit_price=exit_price, qty=qty, fees=fees,
                slippage=gross_raw-gross_fill, funding=funding,
                pnl=gross_fill-fees-funding)


@pytest.mark.parametrize('symbol', SYMBOLS)
@pytest.mark.parametrize('side', ('long','short'))
def test_agent7_decimal_cost_oracle_and_no_order_authority(symbol, side, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('offline computation attempted network')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    payload = request(symbol, side)
    before = copy.deepcopy(payload)
    actual = evaluate(payload, now_ms=1300)
    for key, value in oracle(side).items():
        assert actual[key] == pytest.approx(float(value), rel=1e-12, abs=1e-12)
    assert payload == before
    assert actual['request_sha256'] == digest(payload)
    assert actual['strategy_revision'] == payload['strategy_revision']
    assert actual['execution_authority'] is False
    assert actual['trading_authorized'] is False
    assert actual['training_authorized'] is False
    assert actual['source_authenticity'] == 'NOT_EVALUATED'


@pytest.mark.parametrize('boundary', ('before','after','uncommitted'))
def test_agent7_actual_worker_loss_and_retry_has_one_durable_trade(tmp_path, boundary):
    ledger = PaperLedger.create(tmp_path/'paper.sqlite')
    payload = request()
    input_path = tmp_path/'request.json'
    input_path.write_bytes(canonical(payload))
    code = '''
import json,os,sqlite3,sys
from pathlib import Path
from strattester.research.quote_paper import PaperLedger
path,input_path,boundary=sys.argv[1:]
payload=json.loads(Path(input_path).read_bytes())
if boundary=='after': PaperLedger(path).append(payload,now_ms=1300)
if boundary=='uncommitted':
    con=sqlite3.connect(path);con.execute('BEGIN IMMEDIATE')
    con.execute('INSERT INTO receipts VALUES(?,?)',('interrupted-receipt','a'*64))
os._exit(71)
'''
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=str(root))
    child = subprocess.run([sys.executable,'-c',code,str(ledger.path),str(input_path),boundary],
                           cwd=tmp_path, env=env, capture_output=True, timeout=15)
    assert child.returncode == 71, child.stderr.decode(errors='replace')
    recovered = PaperLedger(ledger.path)
    first = recovered.append(payload, now_ms=1300)
    assert recovered.append(copy.deepcopy(payload), now_ms=999999) == first
    assert recovered.snapshot()['validated_count'] == 1
    with closing(sqlite3.connect(ledger.path)) as con:
        assert con.execute('SELECT COUNT(*) FROM trades').fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM receipts WHERE receipt_id='interrupted-receipt'").fetchone()[0] == 0


def test_agent7_same_signal_cannot_be_reexecuted_under_new_request(tmp_path):
    ledger = PaperLedger.create(tmp_path/'paper.sqlite')
    payload = request(); ledger.append(payload, now_ms=1300)
    changed = copy.deepcopy(payload); changed['request_id'] = 'operation-2'
    with pytest.raises(ValueError): ledger.append(changed, now_ms=1300)
    conflict = copy.deepcopy(payload); conflict['policy']['fee_bps'] += 1
    with pytest.raises(ValueError): ledger.append(conflict, now_ms=1300)
    assert ledger.snapshot()['validated_count'] == 1


@pytest.mark.parametrize('field', ('pnl','request_sha256','trading_authorized'))
def test_agent7_rehashed_persisted_result_cannot_forge_retry_success(tmp_path, field):
    ledger = PaperLedger.create(tmp_path/'paper.sqlite')
    payload = request(); ledger.append(payload, now_ms=1300)
    with closing(sqlite3.connect(ledger.path)) as con, con:
        result = json.loads(con.execute('SELECT result FROM trades').fetchone()[0])
        result[field] = {'pnl':999.,'request_sha256':'c'*64,'trading_authorized':True}[field]
        con.execute('UPDATE trades SET result=?,result_sha256=?', (canonical(result).decode(),digest(result)))
    with pytest.raises(ValueError): PaperLedger(ledger.path).append(payload, now_ms=1300)


@pytest.mark.parametrize('mutation', ('live','version','funding-gap','digest'))
def test_agent7_invalid_input_cannot_commit_partial_paper_events(tmp_path, mutation):
    ledger = PaperLedger.create(tmp_path/'paper.sqlite'); payload = request()
    if mutation == 'live': payload['evidence_class'] = 'VERIFIED_LIVE'
    elif mutation == 'version': payload['schema'] = 'stratt.paper.quote.request.v2'
    elif mutation == 'funding-gap': payload['funding']['events'] = []
    else: payload['quotes'][0]['ask'] = 101.
    if mutation == 'funding-gap':
        del payload['funding']['sha256']; payload['funding']['sha256'] = digest(payload['funding'])
    with pytest.raises(ValueError): ledger.append(payload, now_ms=1300)
    with closing(sqlite3.connect(ledger.path)) as con:
        assert con.execute('SELECT COUNT(*) FROM trades').fetchone()[0] == 0
        assert con.execute('SELECT COUNT(*) FROM receipts').fetchone()[0] == 0
