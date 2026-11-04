"""SYNTHETIC fixtures only: hand-accounted paper research, no exchange execution."""
import copy,hashlib,json,sqlite3
import pytest
from strattester.research.quote_paper import evaluate,PaperLedger

def seal(v):
 v['sha256']=hashlib.sha256(json.dumps({k:x for k,x in v.items() if k!='sha256'},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest();return v

def fixture(side='long',symbol='ETHUSDT'):
 def rec(id,**kw):return seal(dict(receipt_id=id,symbol=symbol,source_id='SYNTHETIC_TEST_INPUT',raw_sha256='a'*64,**kw))
 return dict(schema='stratt.paper.quote.request.v1',request_id='r1',strategy='SYNTHETIC_TEST_INPUT',strategy_revision='b'*40,evidence_class='SYNTHETIC',symbol=symbol,units={'price':'USDT/'+symbol[:-4],'qty':symbol[:-4]},policy=dict(notional=101.,fee_bps=10.,slippage_bps=100.,latency_ms=10,max_quote_age_ms=1000,max_hold_ms=1000),signal=rec('s1',decision_ms=1000,observed_ms=1000,expires_ms=1500,side=side),close_signal=rec('s2',decision_ms=1200,observed_ms=1200,expires_ms=1500),quotes=[rec('q1',epoch='epoch1',sequence=1,event_ms=1010,observed_ms=1011,bid=99.,ask=100.),rec('q2',epoch='epoch1',sequence=2,event_ms=1210,observed_ms=1211,bid=110.,ask=111.)],funding=rec('f1',kind='COMPLETE_INTERVAL',observed_ms=1000,previous_ms=0,next_ms=2000,interval_ms=2000,events=[]))

def test_long_hand_accounting():
 r=evaluate(fixture(),now_ms=1300)
 assert r['qty']==1 and r['signed_qty']==1 and r['entry_price']==101 and r['exit_price']==108.9
 assert r['gross_raw']==10 and r['slippage']==pytest.approx(2.1) and r['fees']==pytest.approx(.2099)
 assert r['funding']==0 and r['pnl']==pytest.approx(7.6901)
 assert not r['trading_authorized'] and r['source_authenticity']=='NOT_EVALUATED'

def test_short_signed_funding():
 p=fixture('short');p['policy']['notional']=98.01
 p['funding']=seal(dict(receipt_id='f1',symbol='ETHUSDT',source_id='SYNTHETIC_TEST_INPUT',raw_sha256='a'*64,kind='COMPLETE_EVENTS',observed_ms=1200,previous_ms=0,next_ms=2200,interval_ms=1100,events=[seal(dict(receipt_id='fundevent',symbol='ETHUSDT',source_id='SYNTHETIC_TEST_INPUT',raw_sha256='b'*64,event_ms=1100,observed_ms=1101,rate=.01,mark_price=105.))]))
 r=evaluate(p,now_ms=1300)
 assert r['qty']==pytest.approx(1) and r['signed_qty']==pytest.approx(-1)
 assert r['entry_price']==pytest.approx(98.01) and r['exit_price']==pytest.approx(112.11)
 assert r['gross_raw']==pytest.approx(-12) and r['slippage']==pytest.approx(2.1)
 assert r['funding']==pytest.approx(-1.05) and r['pnl']==pytest.approx(-13.26012)

@pytest.mark.parametrize('change',[lambda p:p.update(schema='wrong'),lambda p:p.update(symbol='UNKNOWN'),lambda p:p['units'].update(price='BTC'),lambda p:p['quotes'][1].update(epoch='other'),lambda p:p['quotes'][1].update(sequence=1),lambda p:p['quotes'][0].update(event_ms=1000),lambda p:p['quotes'][0].update(observed_ms=1005),lambda p:p['quotes'][1].update(observed_ms=1501),lambda p:p['quotes'][1].update(event_ms=1400),lambda p:p['quotes'][0].update(bid=float('nan')),lambda p:p['quotes'][0].update(ask=98),lambda p:p['funding'].update(next_ms=1210),lambda p:p['funding'].update(events=[{}]),lambda p:p['quotes'][0].update(extra=True),lambda p:p['close_signal'].update(decision_ms=1010)])
def test_causality_or_schema_rejects_even_if_resealed(change):
 p=fixture();change(p)
 for k in ('signal','close_signal','funding'):
  try:seal(p[k])
  except ValueError:pass
 for q in p['quotes']:
  try:seal(q)
  except ValueError:pass
 with pytest.raises(ValueError):evaluate(p,now_ms=1300)

def test_digest_mutation_stale_and_ten_units():
 p=fixture();p['quotes'][0]['ask']=101
 with pytest.raises(ValueError):evaluate(p,now_ms=1300)
 with pytest.raises(ValueError):evaluate(fixture(),now_ms=3000)
 for s in ('BTC','ETH','SOL','XRP','BNB','DOGE','ADA','AVAX','LINK','DOT'):
  r=evaluate(fixture(symbol=s+'USDT'),now_ms=1300);assert r['units']['qty']==s

def test_ledger_idempotent_conflict_and_partial_failure(tmp_path):
 path=tmp_path/'new.sqlite';ledger=PaperLedger.create(path);p=fixture();r=ledger.append(p,now_ms=1300)
 assert ledger.append(p,now_ms=100000)==r
 bad=fixture();bad['policy']['fee_bps']=20
 with pytest.raises(ValueError):ledger.append(bad,now_ms=1300)
 p2=fixture();p2['request_id']='r2';p2['quotes'][0]['ask']=101;seal(p2['quotes'][0])
 with pytest.raises(ValueError):ledger.append(p2,now_ms=1300)
 with sqlite3.connect(path) as c:assert c.execute('select count(*) from trades').fetchone()[0]==1
 with pytest.raises(FileExistsError):PaperLedger.create(path)

def test_transaction_failure_rolls_back_receipts(tmp_path):
 path=tmp_path/'new.sqlite';ledger=PaperLedger.create(path)
 with sqlite3.connect(path) as c:c.execute("CREATE TRIGGER deny_trade BEFORE INSERT ON trades BEGIN SELECT RAISE(ABORT,'SYNTHETIC_TEST_FAILURE'); END")
 with pytest.raises(sqlite3.IntegrityError):ledger.append(fixture(),now_ms=1300)
 with sqlite3.connect(path) as c:assert c.execute('select count(*) from receipts').fetchone()[0]==0


@pytest.mark.parametrize('change',[
 lambda p:p['quotes'][0].update(symbol='BTCUSDT'),
 lambda p:p['funding'].update(previous_ms=1011),
 lambda p:p['funding'].update(interval_ms=1,next_ms=2**53-1),
 lambda p:p['quotes'][1].update(receipt_id='q1'),
 lambda p:p['quotes'][1].update(event_ms=1009),
 lambda p:p['signal'].update(observed_ms=1001),
 lambda p:p['policy'].update(latency_ms=0),
 lambda p:p['policy'].update(slippage_bps=-1),
 lambda p:p['policy'].update(notional=float('inf')),
 lambda p:p['funding'].update(verified=True),
 lambda p:p['close_signal'].update(expires_ms=1209)])
def test_additional_symbol_bounds_and_claims_rejected(change):
 p=fixture();change(p)
 for r in [p['signal'],p['close_signal'],*p['quotes'],p['funding']]:seal(r)
 with pytest.raises(ValueError):evaluate(p,now_ms=1300)

def test_funding_hole_rejected_even_with_fresh_hash():
 p=fixture();p['funding'].update(kind='COMPLETE_EVENTS',interval_ms=500,events=[]);seal(p['funding'])
 with pytest.raises(ValueError):evaluate(p,now_ms=1300)

def test_ledger_receipt_conflict_rolls_back_new_receipts(tmp_path):
 path=tmp_path/'ledger.sqlite';ledger=PaperLedger.create(path);ledger.append(fixture(),now_ms=1300)
 p=fixture();p['request_id']='r2';p['signal']['receipt_id']='new-signal';seal(p['signal']);p['quotes'][0]['ask']=101;seal(p['quotes'][0])
 with pytest.raises(ValueError):ledger.append(p,now_ms=1300)
 with sqlite3.connect(path) as c:assert c.execute("select count(*) from receipts where receipt_id='new-signal'").fetchone()[0]==0

def test_ledger_persists_reopen_and_rejects_hardlinks(tmp_path):
 import os
 path=tmp_path/'ledger.sqlite';ledger=PaperLedger.create(path);r=ledger.append(fixture(),now_ms=1300)
 assert PaperLedger(path).append(fixture(),now_ms=100000)==r
 os.link(path,tmp_path/'alias.sqlite')
 with pytest.raises(ValueError):PaperLedger(path)

def test_concurrent_identical_appends_have_one_trade(tmp_path):
 from concurrent.futures import ThreadPoolExecutor
 path=tmp_path/'ledger.sqlite';PaperLedger.create(path)
 with ThreadPoolExecutor(max_workers=4) as pool:
  results=list(pool.map(lambda _:PaperLedger(path).append(fixture(),now_ms=1300),range(4)))
 assert all(x==results[0] for x in results)
 with sqlite3.connect(path) as c:assert c.execute('select count(*) from trades').fetchone()[0]==1


def test_signal_receipt_cannot_execute_twice_under_new_request_id(tmp_path):
 ledger=PaperLedger.create(tmp_path/'ledger.sqlite');ledger.append(fixture(),now_ms=1300)
 p=fixture();p['request_id']='different-request'
 with pytest.raises(ValueError):ledger.append(p,now_ms=1300)


def test_zero_funding_schedule_must_have_been_observed_by_entry():
 p=fixture();p['funding']['observed_ms']=1012;seal(p['funding'])
 with pytest.raises(ValueError):evaluate(p,now_ms=1300)


def test_duplicate_retry_never_returns_a_tampered_durable_result(tmp_path):
 path=tmp_path/'ledger.sqlite';ledger=PaperLedger.create(path);p=fixture();ledger.append(p,now_ms=1300)
 with sqlite3.connect(path) as c:
  stored=json.loads(c.execute('SELECT result FROM trades').fetchone()[0]);stored['pnl']+=1000
  c.execute('UPDATE trades SET result=?',(json.dumps(stored),))
 with pytest.raises(ValueError):PaperLedger(path).append(p,now_ms=100000)


def test_observed_hold_duration_cannot_exceed_policy_even_with_fresh_event_times():
 p=fixture();p['policy']['max_hold_ms']=220;p['policy']['max_quote_age_ms']=2000
 p['quotes'][1]['observed_ms']=1400;seal(p['quotes'][1])
 with pytest.raises(ValueError):evaluate(p,now_ms=1400)


def test_plain_unrelated_sqlite_database_is_not_adopted(tmp_path):
 path=tmp_path/'foreign.sqlite'
 with sqlite3.connect(path) as c:c.execute('CREATE TABLE unrelated(value TEXT)')
 with pytest.raises(ValueError):PaperLedger(path)


@pytest.mark.parametrize('field,value',[('pnl',999),('trading_authorized',True)])
def test_repaired_result_checksum_still_requires_original_arithmetic(tmp_path,field,value):
 from strattester.research.quote_paper import canonical,digest
 path=tmp_path/'ledger.sqlite';ledger=PaperLedger.create(path);p=fixture();ledger.append(p,now_ms=1300)
 with sqlite3.connect(path) as c:
  result=json.loads(c.execute('SELECT result FROM trades').fetchone()[0]);result[field]=value
  c.execute('UPDATE trades SET result=?,result_sha256=?',(canonical(result).decode(),digest(result)))
 with pytest.raises(ValueError):PaperLedger(path).append(p,now_ms=100000)


def test_corrupted_receipt_mapping_is_not_an_idempotent_success(tmp_path):
 path=tmp_path/'ledger.sqlite';ledger=PaperLedger.create(path);p=fixture();ledger.append(p,now_ms=1300)
 with sqlite3.connect(path) as c:c.execute('UPDATE receipts SET sha256=? WHERE receipt_id=?',('f'*64,'q1'))
 with pytest.raises(ValueError):PaperLedger(path).append(p,now_ms=100000)


def test_connections_close_on_success_retry_and_rejection(tmp_path,monkeypatch):
 original=sqlite3.connect;opened=[]
 def tracked(*a,**kw):
  connection=original(*a,**kw);opened.append(connection);return connection
 monkeypatch.setattr(sqlite3,'connect',tracked)
 try:
  ledger=PaperLedger.create(tmp_path/'ledger.sqlite');p=fixture();ledger.append(p,now_ms=1300);ledger.append(p,now_ms=100000)
  changed=fixture();changed['policy']['fee_bps']=50
  with pytest.raises(ValueError):ledger.append(changed,now_ms=1300)
  assert opened
  for connection in opened:
   with pytest.raises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
 finally:
  for connection in opened:connection.close()


@pytest.mark.parametrize('field,value',[('strategy_revision',''),('strategy_revision','a'*39),('strategy_revision',None),('evidence_class','VERIFIED_LIVE'),('evidence_class',True)])
def test_strategy_revision_and_declared_evidence_are_closed(field,value):
 p=fixture();p[field]=value
 with pytest.raises(ValueError):evaluate(p,now_ms=1300)


def test_synthetic_results_are_labelled_and_strategy_revision_is_bound():
 p=fixture();result=evaluate(p,now_ms=1300)
 assert result['evidence_class']=='SYNTHETIC' and result['strategy_revision']==p['strategy_revision']
 assert result['source_authenticity']=='NOT_EVALUATED'


def test_zero_funding_cannot_claim_a_period_that_was_not_current_when_observed():
 p=fixture();p['funding'].update(previous_ms=1005,next_ms=2005,interval_ms=1000);seal(p['funding'])
 with pytest.raises(ValueError):evaluate(p,now_ms=1300)


@pytest.mark.parametrize('retry_first',[False,True])
def test_corrupt_signal_index_rejected_before_any_further_append(tmp_path,retry_first):
 from contextlib import closing
 path=tmp_path/'ledger.sqlite';ledger=PaperLedger.create(path);p=fixture();ledger.append(p,now_ms=1300)
 with closing(sqlite3.connect(path)) as c,c:c.execute("UPDATE trades SET signal_id='corrupted-index'")
 if retry_first:
  with pytest.raises(ValueError):ledger.append(p,now_ms=100000)
 new=fixture();new['request_id']='new-request'
 with pytest.raises(ValueError):ledger.append(new,now_ms=1300)
 with closing(sqlite3.connect(path)) as c:assert c.execute('SELECT COUNT(*) FROM trades').fetchone()[0]==1


@pytest.mark.parametrize('corruption',['result_arithmetic','request_hash','result_request_binding','signal_binding'])
def test_new_request_revalidates_all_durable_trade_bindings(tmp_path,corruption):
 from contextlib import closing
 from strattester.research.quote_paper import canonical,digest
 path=tmp_path/'ledger.sqlite';ledger=PaperLedger.create(path);ledger.append(fixture(),now_ms=1300)
 with closing(sqlite3.connect(path)) as c,c:
  if corruption=='request_hash':c.execute('UPDATE trades SET request_sha256=?',('c'*64,))
  else:
   result=json.loads(c.execute('SELECT result FROM trades').fetchone()[0])
   if corruption=='result_arithmetic':result['pnl']+=1000
   elif corruption=='result_request_binding':result['request_sha256']='c'*64
   else:result['receipt_bindings'][0]['receipt_id']='other-signal'
   c.execute('UPDATE trades SET result=?,result_sha256=?',(canonical(result).decode(),digest(result)))
 new=fixture();new['request_id']='new-request';new['signal']['receipt_id']='fresh-signal';seal(new['signal'])
 with pytest.raises(ValueError):ledger.append(new,now_ms=1300)
 with closing(sqlite3.connect(path)) as c:assert c.execute('SELECT COUNT(*) FROM trades').fetchone()[0]==1


@pytest.mark.parametrize('field',['request','result','signal_id','request_sha256','admitted_ms'])
def test_oversized_or_invalid_durable_columns_rejected_before_evaluation(tmp_path,monkeypatch,field):
 from contextlib import closing
 import strattester.research.quote_paper as module
 path=tmp_path/'ledger.sqlite';ledger=PaperLedger.create(path);ledger.append(fixture(),now_ms=1300)
 with closing(sqlite3.connect(path)) as c,c:
  c.execute('UPDATE trades SET '+field+'=?',('x'*(module.MAX_CANONICAL_BYTES+1),))
 def forbidden(*args,**kwargs):raise AssertionError('must reject size/type before evaluate')
 monkeypatch.setattr(module,'evaluate',forbidden)
 with pytest.raises(ValueError):ledger.append(fixture(),now_ms=1300)


def test_research_trade_capacity_rejected_before_loading_rows(tmp_path,monkeypatch):
 from contextlib import closing
 import strattester.research.quote_paper as module
 ledger=PaperLedger.create(tmp_path/'ledger.sqlite');ledger.append(fixture(),now_ms=1300)
 monkeypatch.setattr(module,'MAX_LEDGER_TRADES',0)
 def forbidden(*args,**kwargs):raise AssertionError('must reject cap before evaluate')
 monkeypatch.setattr(module,'evaluate',forbidden)
 with pytest.raises(ValueError):ledger.append(fixture(),now_ms=1300)


def test_old_format_is_rejected_without_implicit_migration(tmp_path):
 from contextlib import closing
 path=tmp_path/'ledger.sqlite';PaperLedger.create(path)
 with closing(sqlite3.connect(path)) as c,c:c.execute('PRAGMA user_version=1')
 before=path.read_bytes()
 with pytest.raises(ValueError):PaperLedger(path)
 assert path.read_bytes()==before
