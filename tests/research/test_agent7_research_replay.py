"""Research recovery and MODEL_CONTRACT admission; not Assignment v1 endpoint ACK."""
import copy
import io
import json

import pytest
from strattester.engine.grid_data_first_worker import _IPCLease, ProtocolError, frame
from strattester.research.decision_memory import DecisionTrace, ObservedOutcome
from strattester.research.learning_event_log import LearningEventLog
from strattester.research.learning_replay import LearningReplayEngine
from strattester.research.organism_checkpoint import export_state, load_checkpoint, save_checkpoint
from strattester.research.organism_controller import ScientificOrganismController
from strattester.research.paper_account import AccountBlocked, PaperAccount
from strattester.research.quote_paper import PaperLedger, canonical, digest
from tests.research.test_paper_account import close_request, inputs, policy, reserve


def history():
    organism = ScientificOrganismController(); log = LearningEventLog()
    for i, utility in enumerate((.5,-.25,.75,-.125), 1):
        ident = 'agent7-decision-'+str(i)
        organism.remember_decision(DecisionTrace(ident,i,'LONG',(),'SYNTHETIC'))
        log.append(ObservedOutcome(ident,'1h',utility,10+i),{'m':1.},regime='SYNTHETIC')
    return organism, log.events()


def test_agent7_checkpoint_resume_matches_uninterrupted_learning_and_retry(tmp_path):
    expected, events = history(); LearningReplayEngine().replay(expected, events)
    partial, _ = history(); LearningReplayEngine().replay(partial, events[:2])
    path = tmp_path/'checkpoint.json'; expected_digest = save_checkpoint(partial,path)
    recovered = ScientificOrganismController()
    assert load_checkpoint(recovered,path) == expected_digest
    result = LearningReplayEngine().replay(recovered,events)
    assert (result.applied,result.skipped,result.end_sequence) == (2,2,4)
    assert canonical(export_state(recovered)) == canonical(export_state(expected))
    before = canonical(export_state(recovered))
    retry = LearningReplayEngine().replay(recovered,events)
    assert retry.applied == 0 and retry.skipped == 4
    assert canonical(export_state(recovered)) == before


@pytest.mark.parametrize('kind', ('checksum','schema','unsafe-state'))
def test_agent7_invalid_checkpoint_cannot_partially_mutate_live_state(tmp_path, kind):
    organism, events = history(); LearningReplayEngine().replay(organism,events[:1])
    path = tmp_path/'checkpoint.json'; save_checkpoint(organism,path)
    envelope = json.loads(path.read_bytes())
    if kind == 'schema': envelope['payload']['schema_version'] = 999
    else: envelope['payload']['brain']['potential'] = float('inf')
    if kind != 'checksum':
        # The current checkpoint checksum format allows JSON Infinity; semantic
        # validation must still reject a rechecksummed nonfinite state.
        import hashlib
        from strattester.research.organism_checkpoint import _canonical
        envelope['sha256'] = hashlib.sha256(_canonical(envelope['payload']).encode()).hexdigest()
    path.write_text(json.dumps(envelope),encoding='utf-8')
    target = ScientificOrganismController(); target.brain.potential = .123
    before = copy.deepcopy(export_state(target))
    with pytest.raises(ValueError): load_checkpoint(target,path)
    assert export_state(target) == before


def test_agent7_uncertain_collateral_survives_reopen_and_reconcile(tmp_path):
    account = PaperAccount.create(tmp_path/'account',policy(),require_current=lambda:True)
    payload, prior = inputs(); reserve(account,payload,prior)
    account.mark_uncertain(payload['request_id'],'RESTART',now_ms=1100)
    before = account.snapshot()
    recovered = PaperAccount.open(account.root,policy(),ownership=account.ownership,require_current=lambda:True)
    recovered.reconcile(now_ms=10000)
    after = recovered.snapshot()
    assert after['reserved_usdt'] == before['reserved_usdt'] > 0
    assert after['cash_usdt'] == before['cash_usdt']
    assert after['reservations'][0]['status'] == 'UNCERTAIN'
    assert PaperLedger(account.ledger_path).snapshot()['validated_count'] == 0
    with pytest.raises(AccountBlocked): reserve(recovered,payload,prior,now=10000)


@pytest.mark.parametrize('reason', ('STALE_WORKER','NO_QUORUM','REVOKED'))
def test_agent7_model_authority_denial_blocks_paper_commit_without_freeing_cash(tmp_path, reason):
    # The boolean is a MODEL callback, never an authenticated A2 endpoint.
    authority = {'allowed':True, 'reason':None}
    account = PaperAccount.create(tmp_path/'account',policy(),require_current=lambda:authority['allowed'])
    payload, prior = inputs(); reserve(account,payload,prior)
    account.record_entry(payload['request_id'],payload['quotes'][0],now_ms=1011)
    closing = close_request(account,payload)
    reserved = account.snapshot()['reserved_usdt']
    before = account.account_path.read_bytes()
    authority.update(allowed=False,reason=reason)
    with pytest.raises(AccountBlocked,match='ACCOUNT_REVOKED'):
        account.close_trade(closing,now_ms=1300)
    assert account.account_path.read_bytes() == before
    assert PaperLedger(account.ledger_path).snapshot()['validated_count'] == 0
    authority['allowed'] = True
    assert account.snapshot()['reserved_usdt'] == reserved > 0


def test_agent7_model_reassignment_rejects_old_generation_before_rpc():
    nonce = 'a'*64
    assigned = dict(id='synthetic-job',lease_owner='worker-b',lease_generation=2,payload={'dataset':'b'*64})
    writer = io.BytesIO()
    lease = _IPCLease(io.BytesIO(frame(nonce,0,'INIT',{'job':assigned})),writer)
    stale = dict(assigned,lease_owner='worker-a',lease_generation=1)
    with pytest.raises(ProtocolError): lease.renew(stale)
    with pytest.raises(ProtocolError): lease.publish(stale,1,'COMPLETED',{})
    assert writer.getvalue() == b''


def test_agent7_model_no_quorum_ack_cannot_publish_completion():
    nonce = 'a'*64
    job = dict(id='synthetic-job',lease_owner='worker-b',lease_generation=2,payload={'dataset':'b'*64})
    checkpoint = {'cursor':3}; body = dict(sequence=1,state='COMPLETED',checkpoint=checkpoint)
    reply = dict(accepted=False,state='COMPLETED',sha256=digest(body),request_sha256=digest(job['payload']))
    reader = io.BytesIO(frame(nonce,0,'INIT',{'job':job})+
                        frame(nonce,1,'ACK',{'op':'CHECKPOINT','value':reply}))
    writer = io.BytesIO(); lease = _IPCLease(reader,writer)
    with pytest.raises(ProtocolError,match='PROCESS_LEASE_FENCED'):
        lease.publish(job,1,'COMPLETED',checkpoint)
    assert lease.last is None
    with pytest.raises(ProtocolError): lease.finish()
    assert b'"DONE"' not in writer.getvalue()
