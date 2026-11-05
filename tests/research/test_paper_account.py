"""Actual native accounting with synthetic causal inputs; no market/network effects."""
import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from tests.test_quote_paper import fixture, seal
from strattester.research.paper_account import PaperAccount, AccountBlocked


def policy(**overrides):
    value = dict(schema='stratt.paper.account-policy.v1', mode='LAB_SIMULATION',
                 long_only=True, initial_cash_usdt=10000., notional_usdt=101.,
                 max_reserved_usdt=2000., max_positions=10, max_drawdown_fraction=.5,
                 max_quote_age_ms=1000, max_spread_bps=250., fee_bps=10.,
                 slippage_bps=100., latency_ms=10, entry_wait_ms=500,
                 exit_wait_ms=500, hold_ms=100)
    value.update(overrides); return value


def inputs(symbol='ETHUSDT', ident='r1'):
    value = fixture(symbol=symbol); value['request_id'] = ident
    value['funding'].update(next_ms=10000, interval_ms=10000); seal(value['funding'])
    quote = copy.deepcopy(value['quotes'][0])
    quote.update(receipt_id=ident+'_prior', sequence=0, event_ms=990, observed_ms=991); seal(quote)
    return value, quote


def reserve(account, request, prior, now=1000):
    proposal=copy.deepcopy(request['signal'])
    result=account.reserve(request['request_id'], signal=proposal,
                           strategy=request['strategy'], strategy_revision=request['strategy_revision'],
                           evidence_class=request['evidence_class'], reference_quote=prior,
                           funding=request['funding'], now_ms=now)
    if result['accepted']:
        from strattester.research.quote_paper import digest
        decision=dict(proposal,receipt_id=request['request_id']+'_decision',source_id='STRATT_PAPER_RISK_DECISION',
            raw_sha256=digest(dict(schema='stratt.paper.risk-decision-input.v1',proposal_sha256=proposal['sha256'],risk_sha256=digest(result))),
            observed_ms=now,decision_ms=now,expires_ms=now+account.policy['entry_wait_ms'])
        seal(decision);account.record_decision(request['request_id'],decision,now_ms=now)
        request['signal']=decision
    return result


def close_request(account, value):
    value = copy.deepcopy(value); value['policy'] = account.execution_policy
    from strattester.research.quote_paper import digest
    record=next(r for r in account.snapshot()['reservations'] if r['id']==value['request_id'])
    now=value['close_signal']['decision_ms']
    value['close_signal'].update(source_id='STRATT_PAPER_CLOSE_DECISION',
        raw_sha256=digest(dict(schema='stratt.paper.close-decision-input.v1',opening_decision_sha256=record['decision']['sha256'],
            entry_quote_sha256=record['entry_quote']['sha256'],risk_sha256=digest(record['risk_receipt']),hold_ms=account.policy['hold_ms'])),
        expires_ms=now+account.policy['exit_wait_ms'])
    seal(value['close_signal'])
    account.record_exit_decision(value['request_id'],value['close_signal'],now_ms=now)
    return value


def test_native_financial_result_is_the_only_settlement_calculator(tmp_path):
    account = PaperAccount.create(tmp_path/'owned', policy(), require_current=lambda: True)
    request, prior = inputs(); accepted = reserve(account, request, prior)
    assert accepted['accepted'] is True and accepted['collateral_usdt'] == pytest.approx(101.101)
    account.record_entry('r1', request['quotes'][0], now_ms=1011)
    result = account.close_trade(close_request(account, request), now_ms=1300)
    assert result['pnl'] == pytest.approx(7.6901)
    view = account.snapshot()
    assert view['cash_usdt'] == pytest.approx(10007.6901) and view['reserved_usdt'] == 0
    assert view['open_positions'] == [] and view['closed_count'] == 1
    assert view['trading_authorized'] is False and view['source_authenticity'] == 'NOT_EVALUATED'
    assert account.verified_paper_snapshot()['rows'][0]['result'] == result
    assert account.close_trade(close_request(account, request), now_ms=9000) == result
    assert account.snapshot()['cash_usdt'] == view['cash_usdt']


def test_unknown_externally_appended_native_trade_blocks_every_new_admission(tmp_path):
    from strattester.research.quote_paper import PaperLedger
    account = PaperAccount.create(tmp_path/'owned', policy(), require_current=lambda: True)
    unknown, _ = inputs('BTCUSDT', 'foreign')
    PaperLedger(account.ledger_path).append(unknown, now_ms=1300)
    value, prior = inputs()
    with pytest.raises(AccountBlocked): reserve(account, value, prior)
    with pytest.raises(AccountBlocked): account.snapshot()
    with pytest.raises(AccountBlocked): account.verified_paper_snapshot()


@pytest.mark.parametrize('mutation', [lambda p:p.update(long_only=False),
    lambda p:p.update(initial_cash_usdt=float('nan')),lambda p:p.update(max_positions=True),
    lambda p:p.update(max_positions=11),lambda p:p.update(extra='PRIVATE'),
    lambda p:p.update(notional_usdt=0),lambda p:p.update(max_drawdown_fraction=1.)])
def test_invalid_policy_precedes_any_file_creation(tmp_path, mutation):
    value = policy(); mutation(value)
    with pytest.raises(AccountBlocked): PaperAccount.create(tmp_path/'owned', value, require_current=lambda: True)
    assert not (tmp_path/'owned').exists()


def test_short_unknown_funding_stale_and_wide_quote_are_actual_risk_denials(tmp_path):
    for index, reason in enumerate(('short', 'funding', 'stale', 'spread')):
        account = PaperAccount.create(tmp_path/str(index), policy(), require_current=lambda: True)
        value, prior = inputs()
        if reason == 'short': value['signal']['side'] = 'short'; seal(value['signal'])
        if reason == 'funding': value['funding'] = None
        if reason == 'stale': prior.update(event_ms=1, observed_ms=1); seal(prior)
        if reason == 'spread': prior.update(bid=50); seal(prior)
        receipt = reserve(account, value, prior, now=1002 if reason=='stale' else 1000)
        assert receipt['accepted'] is False and account.snapshot()['reserved_usdt'] == 0
        assert account.snapshot()['closed_count'] == 0


def test_same_symbol_and_concurrent_cash_reservations_cannot_overspend(tmp_path):
    account = PaperAccount.create(tmp_path/'owned', policy(initial_cash_usdt=150., max_reserved_usdt=150., max_drawdown_fraction=.99), require_current=lambda: True)
    value, prior = inputs(); other, other_prior = inputs('BTCUSDT', 'r2')
    # Native receipts must have unique identities across independent decisions.
    for key in ('signal', 'close_signal', 'funding'):
        other[key]['receipt_id'] = 'r2_'+key; seal(other[key])
    for index, quote in enumerate(other['quotes']): quote['receipt_id'] = 'r2_q'+str(index); seal(quote)
    reopened = PaperAccount.open(account.root, policy(initial_cash_usdt=150., max_reserved_usdt=150., max_drawdown_fraction=.99), ownership=account.ownership, require_current=lambda: True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args: reserve(*args), [(account,value,prior),(reopened,other,other_prior)]))
    assert sum(row['accepted'] for row in results) == 1
    assert account.snapshot()['reserved_usdt'] == pytest.approx(101.101)


def test_entry_must_be_a_new_later_quote_and_cannot_be_reselected(tmp_path):
    account = PaperAccount.create(tmp_path/'owned', policy(), require_current=lambda: True)
    value, prior = inputs(); reserve(account,value,prior)
    for changes in ({'event_ms':1000,'observed_ms':1001}, {'sequence':0}, {'epoch':'other'}, {'observed_ms':1009}):
        bad = copy.deepcopy(value['quotes'][0]); bad.update(changes); seal(bad)
        with pytest.raises(AccountBlocked): account.record_entry('r1',bad,now_ms=1011)
    account.record_entry('r1',value['quotes'][0],now_ms=1011)
    changed = copy.deepcopy(value['quotes'][0]); changed['ask']=100.1;seal(changed)
    with pytest.raises(AccountBlocked): account.record_entry('r1',changed,now_ms=1011)
    assert len(account.snapshot()['open_positions']) == 1


def test_crash_after_native_commit_reconciles_once_without_reexecution(tmp_path,monkeypatch):
    account = PaperAccount.create(tmp_path/'owned', policy(), require_current=lambda: True)
    value, prior = inputs(); reserve(account,value,prior); account.record_entry('r1',value['quotes'][0],now_ms=1011)
    def crash(*args): raise RuntimeError('SYNTHETIC_CRASH_AFTER_NATIVE_COMMIT')
    monkeypatch.setattr(account,'_after_native_commit',crash)
    with pytest.raises(AccountBlocked): account.close_trade(close_request(account,value),now_ms=1300)
    # The close intent and collateral survive independently of native commit.
    recovered = PaperAccount.open(account.root,policy(),ownership=account.ownership,require_current=lambda:True)
    recovered.reconcile(now_ms=1400)
    balance = recovered.snapshot()['cash_usdt']; recovered.reconcile(now_ms=1500)
    assert recovered.snapshot()['cash_usdt'] == balance == pytest.approx(10007.6901)
    assert recovered.snapshot()['reserved_usdt'] == 0


def test_uncertain_reservation_survives_restart_and_never_releases_automatically(tmp_path):
    account = PaperAccount.create(tmp_path/'owned', policy(), require_current=lambda: True)
    value, prior = inputs(); reserve(account,value,prior)
    account.mark_uncertain('r1','SOURCE_GAP',now_ms=1100)
    recovered = PaperAccount.open(account.root,policy(),ownership=account.ownership,require_current=lambda:True)
    recovered.reconcile(now_ms=10000)
    assert recovered.snapshot()['reserved_usdt'] == pytest.approx(101.101)
    assert recovered.snapshot()['reservations'][0]['status'] == 'UNCERTAIN'
    with pytest.raises(AccountBlocked): reserve(recovered,value,prior,now=10000)
    assert recovered.snapshot()['reserved_usdt'] == pytest.approx(101.101)


def test_corrupt_journal_foreign_replacement_and_revocation_block_without_repair(tmp_path):
    account = PaperAccount.create(tmp_path/'owned',policy(),require_current=lambda:True)
    value, prior = inputs();reserve(account,value,prior)
    with sqlite3.connect(account.account_path) as con: con.execute("UPDATE events SET digest=? WHERE sequence=1",('a'*64,))
    with pytest.raises(AccountBlocked): account.snapshot()
    assert account.ledger_path.exists()
    revoked = PaperAccount.create(tmp_path/'revoked',policy(),require_current=lambda:True)
    revoked.require_current = lambda:False
    with pytest.raises(AccountBlocked): reserve(revoked,value,prior)


def test_existing_namespace_and_unadmitted_open_are_not_adopted(tmp_path):
    root = tmp_path/'foreign';root.mkdir();(root/'foreign').write_bytes(b'FOREIGN')
    with pytest.raises(AccountBlocked): PaperAccount.create(root,policy(),require_current=lambda:True)
    with pytest.raises(AccountBlocked): PaperAccount.open(root,policy(),ownership={},require_current=lambda:True)
    assert (root/'foreign').read_bytes() == b'FOREIGN'


def test_rehashed_zero_collateral_forgery_cannot_make_cash_spendable(tmp_path):
    from strattester.research.quote_paper import canonical,digest
    account = PaperAccount.create(tmp_path/'owned',policy(initial_cash_usdt=150.,max_reserved_usdt=150.,max_drawdown_fraction=.99),require_current=lambda:True)
    value, prior=inputs();reserve(account,value,prior)
    with sqlite3.connect(account.account_path) as connection:
        event=json.loads(connection.execute('SELECT body FROM events WHERE sequence=1').fetchone()[0])
        event['record']['collateral']='0';event['record']['risk_receipt']['collateral_usdt']=0.
        connection.execute('UPDATE events SET body=?,digest=? WHERE sequence=1',(canonical(event).decode(),digest(event)))
        connection.execute('UPDATE reservations SET body=? WHERE id=?',(canonical(event['record']).decode(),'r1'))
    second, second_prior=inputs('BTCUSDT','r2')
    with pytest.raises(AccountBlocked):reserve(account,second,second_prior)


def test_risk_reservation_does_not_itself_authorize_entry_before_durable_decision(tmp_path):
    account=PaperAccount.create(tmp_path/'owned',policy(),require_current=lambda:True)
    value,prior=inputs()
    receipt=account.reserve('r1',signal=value['signal'],strategy=value['strategy'],strategy_revision=value['strategy_revision'],
        evidence_class=value['evidence_class'],reference_quote=prior,funding=value['funding'],now_ms=1000)
    assert receipt['accepted']
    with pytest.raises(AccountBlocked):account.record_entry('r1',value['quotes'][0],now_ms=1011)
    bad=copy.deepcopy(value['signal']);bad.update(receipt_id='final',source_id='STRATT_PAPER_RISK_DECISION')
    seal(bad)
    with pytest.raises(AccountBlocked):account.record_decision('r1',bad,now_ms=1000)


def test_exit_quote_cannot_be_selected_before_durable_close_decision(tmp_path):
    account=PaperAccount.create(tmp_path/'owned',policy(),require_current=lambda:True)
    value,prior=inputs();reserve(account,value,prior);account.record_entry('r1',value['quotes'][0],now_ms=1011)
    request=copy.deepcopy(value);request['policy']=account.execution_policy
    with pytest.raises(AccountBlocked):account.close_trade(request,now_ms=1300)


def test_pending_reservations_also_reserve_finite_native_ledger_slots(tmp_path,monkeypatch):
    from strattester.research import paper_account
    monkeypatch.setattr(paper_account,'MAX_CLOSED',1)
    account=PaperAccount.create(tmp_path/'owned',policy(),require_current=lambda:True)
    first,prior=inputs();assert reserve(account,first,prior)['accepted']
    second,second_prior=inputs('BTCUSDT','r2');denied=reserve(account,second,second_prior)
    assert denied['accepted'] is False and denied['reason']=='LEDGER_CAPACITY'
    assert account.snapshot()['reserved_usdt']==pytest.approx(101.101)


def test_revocation_after_last_native_audit_prevents_irreversible_append(tmp_path,monkeypatch):
    from strattester.research.quote_paper import PaperLedger
    live=[True]
    account=PaperAccount.create(tmp_path/'owned',policy(),require_current=lambda:live[0])
    value,prior=inputs();reserve(account,value,prior)
    account.record_entry('r1',value['quotes'][0],now_ms=1011)
    closing=close_request(account,value)
    original=account._native;calls=[0]
    def audit_then_revoke(records):
        result=original(records);calls[0]+=1
        if calls[0]==2:live[0]=False
        return result
    monkeypatch.setattr(account,'_native',audit_then_revoke)
    with pytest.raises(AccountBlocked,match='ACCOUNT_REVOKED'):account.close_trade(closing,now_ms=1300)
    assert PaperLedger(account.ledger_path).snapshot()['validated_count']==0
    live[0]=True;monkeypatch.setattr(account,'_native',original)
    record=account.snapshot()['reservations'][0]
    assert record['status']=='CLOSE_READY' and account.snapshot()['reserved_usdt']>0


def test_realized_peak_follows_causal_settlement_not_backdated_native_intent(tmp_path,monkeypatch):
    account=PaperAccount.create(tmp_path/'owned',policy(),require_current=lambda:True)
    loss,prior_loss=inputs('ETHUSDT','loss');gain,prior_gain=inputs('BTCUSDT','gain')
    for item in [gain['signal'],gain['close_signal'],gain['funding'],*gain['quotes']]:
        item['receipt_id']='gain_'+item['receipt_id'];seal(item)
    loss['quotes'][1].update(bid=50.,ask=51.);seal(loss['quotes'][1])
    reserve(account,loss,prior_loss);reserve(account,gain,prior_gain)
    for value in (loss,gain):account.record_entry(value['request_id'],value['quotes'][0],now_ms=1011)
    loss=close_request(account,loss);gain=close_request(account,gain)
    original=account._ledger.append
    def fail_before_native(*args,**kwargs):raise RuntimeError('SYNTHETIC_NATIVE_UNAVAILABLE')
    monkeypatch.setattr(account._ledger,'append',fail_before_native)
    with pytest.raises(AccountBlocked):account.close_trade(loss,now_ms=1300)
    monkeypatch.setattr(account._ledger,'append',original)
    account.close_trade(gain,now_ms=1400);peak=account.snapshot()['realized_peak_usdt']
    account.close_trade(loss,now_ms=1500)
    view=account.snapshot();assert view['cash_usdt']==pytest.approx(9956.0396)
    assert view['realized_peak_usdt']==peak==pytest.approx(10007.6901)
    reopened=PaperAccount.open(account.root,policy(),ownership=account.ownership,require_current=lambda:True)
    assert reopened.snapshot()['realized_peak_usdt']==peak


@pytest.mark.parametrize('decision_ms,expires,accepted',[(2000,2500,False),(1491,1500,False),(1489,1500,True),(1489,1989,False)])
def test_risk_decision_cannot_extend_original_strategy_expiry(tmp_path,decision_ms,expires,accepted):
    from strattester.research.quote_paper import digest
    account=PaperAccount.create(tmp_path/'owned',policy(max_quote_age_ms=3000),require_current=lambda:True)
    value,prior=inputs();proposal=value['signal']
    risk=account.reserve('r1',signal=proposal,strategy=value['strategy'],strategy_revision=value['strategy_revision'],
        evidence_class=value['evidence_class'],reference_quote=prior,funding=value['funding'],now_ms=1000)
    decision=dict(proposal,receipt_id='risk_decision',source_id='STRATT_PAPER_RISK_DECISION',
        raw_sha256=digest(dict(schema='stratt.paper.risk-decision-input.v1',proposal_sha256=proposal['sha256'],risk_sha256=digest(risk))),
        decision_ms=decision_ms,observed_ms=decision_ms,expires_ms=expires);seal(decision)
    if accepted:
        account.record_decision('r1',decision,now_ms=decision_ms)
        reopened=PaperAccount.open(account.root,account.policy,ownership=account.ownership,require_current=lambda:True)
        assert reopened.snapshot()['reservations'][0]['decision']['expires_ms']==1500
    else:
        with pytest.raises(AccountBlocked):account.record_decision('r1',decision,now_ms=decision_ms)
        assert account.snapshot()['reservations'][0]['status']=='RESERVED'


def test_rehashed_journal_cannot_extend_original_proposal_ttl(tmp_path):
    from strattester.research.quote_paper import canonical,digest
    account=PaperAccount.create(tmp_path/'owned',policy(max_quote_age_ms=3000),require_current=lambda:True)
    value,prior=inputs();reserve(account,value,prior)
    with sqlite3.connect(account.account_path) as connection:
        event=json.loads(connection.execute('SELECT body FROM events WHERE sequence=2').fetchone()[0])
        event['at_ms']=2000
        decision=event['record']['decision'];decision.update(decision_ms=2000,observed_ms=2000,expires_ms=2500);seal(decision)
        connection.execute('UPDATE events SET body=?,digest=? WHERE sequence=2',(canonical(event).decode(),digest(event)))
        connection.execute('UPDATE reservations SET body=? WHERE id=?',(canonical(event['record']).decode(),'r1'))
    with pytest.raises(AccountBlocked):account.snapshot()
