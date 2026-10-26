from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import runpy
import pytest

def session(tmp_path):
    b=runpy.run_path(str(Path(__file__).with_name('signed_export_fixture.py')))['bundle'](tmp_path)
    from strattester.research.financial_snapshot import canonical_bytes
    p=dict(version=1,manifest_path='manifest.json',manifest_sha256=b['manifest_sha'],snapshot_path='snapshot.json',checkpoint_path='checkpoint.json',checkpoint_sha256=b['checkpoint_sha'],trust_store_path='trust.json',instrument=asdict(b['instrument']),timeframe_ns=b['tf'],horizon_ns=b['tf']*2,available_ns=b['snapshot'].origin_ns+10,policy=asdict(b['policy']),max_work_bytes=512*1024*1024)
    data=canonical_bytes(p);(tmp_path/'session.json').write_bytes(data)
    from strattester.research.financial_session import load_session
    return b,p,load_session(tmp_path/'session.json',sha256(data).hexdigest(),trust_store_sha256=b['trust_sha'],verifier=b['verifier'])

def test_session_real_signed_registry_prediction_and_immutable_report(tmp_path):
    b,p,s=session(tmp_path)
    from strattester.research.financial_session import run_session
    with pytest.raises(ValueError,match='enable'):run_session(s)
    result=run_session(s,enable_research=True)
    assert result['provenance']['config_sha256']==s.config_sha256
    assert result['prediction']['scale']>0 and result['trades']==[]
    from strattester.research.financial_report_export import export_report
    out=tmp_path/'report'
    export_report(result,out)
    assert 'NO-GO' in (out/'report.html').read_text()
    assert (out/'prediction.csv').exists() and (out/'distribution.svg').exists()
    with pytest.raises(FileExistsError):export_report(result,out)

def test_external_pin_and_bundle_path_confinement(tmp_path):
    b,p,s=session(tmp_path)
    from strattester.research.financial_session import load_session
    from strattester.research.financial_snapshot import canonical_bytes
    p['manifest_path']='../manifest.json';data=canonical_bytes(p);(tmp_path/'session.json').write_bytes(data)
    with pytest.raises(ValueError,match='path'):load_session(tmp_path/'session.json',sha256(data).hexdigest(),trust_store_sha256=b['trust_sha'],verifier=b['verifier'])
    with pytest.raises(ValueError,match='SHA256'):load_session(tmp_path/'session.json','0'*64,trust_store_sha256=b['trust_sha'],verifier=b['verifier'])

def test_offline_rejects_connected_capability_and_cancel(tmp_path):
    b,p,s=session(tmp_path)
    from strattester.research.financial_session import run_session
    with pytest.raises(ValueError,match='offline'):run_session(s,enable_research=True,connected_profile=object())
    from strattester.research.financial_training import TrainingCancelled
    with pytest.raises(TrainingCancelled):run_session(s,enable_research=True,cancel=lambda:True)

def test_cli_is_reachable_redacts_errors_and_never_implicitly_enables(tmp_path,capsys):
    b,p,s=session(tmp_path)
    from strattester.research_cli import main
    common=['--config',str(tmp_path/'session.json'),'--config-sha256',s.config_sha256,'--trust-store-sha256',b['trust_sha'],'--openssl-exe',str(b['verifier'].executable),'--openssl-sha256',b['verifier'].executable_sha256,'--scratch-root',str(tmp_path)]
    assert main(['verify',*common])==0
    assert main(['run',*common])==2
    assert 'RESEARCH_ERROR' in capsys.readouterr().out
    assert main(['test-disposable'])==2

def test_explicit_connected_export_signs_public_fixture_then_same_verified_model_route(tmp_path):
    b,p,s=session(tmp_path)
    import sqlite3
    from dataclasses import replace
    from strattester.research.financial_snapshot import canonical_bytes
    from strattester.research.financial_grid_exporter import DDL,SCHEMA_SHA256,history_seal,HistorySource,HistoryProfile,PROFILE
    from strattester.research.financial_signed_export import SourceIdentity
    from strattester.research.financial_session import run_session
    partition=b['policy'].partitions[0]
    rows=[dict(bar=asdict(bar),first_available_ns=bar.available_ns,source_id='fixture-source',coherence_epoch_id='epoch-fixture') for bar in b['snapshot'].bars]
    meta=dict(source_id='fixture-source',snapshot_id='cut-1',coherence_epoch_id='epoch-fixture',schema_sha256=SCHEMA_SHA256,complete=True,first_availability_retained=True,revision_history_retained=True,event_watermark_ns=b['snapshot'].origin_ns,availability_watermark_ns=b['snapshot'].origin_ns,partitions=[asdict(partition)])
    db=tmp_path/'history.db'
    with sqlite3.connect(db) as con:
        for ddl in DDL:con.execute(ddl)
        con.execute('INSERT INTO history_meta VALUES (?)',(canonical_bytes(meta).decode(),))
        con.executemany('INSERT INTO history_rows VALUES (?)',[(canonical_bytes(r).decode(),) for r in rows])
    profile=HistoryProfile(PROFILE,'epoch-fixture',b['snapshot'].origin_ns,(HistorySource('fixture-source','sqlite',str(db),'cut-1',history_seal(meta,rows),(partition,)),))
    s=replace(s,policy=replace(s.policy,sources=(SourceIdentity('fixture-source','sqlite',SCHEMA_SHA256),)))
    metadata=dict(producer_id='fixture-grid',producer_build_sha='a'*40,key_id='rfc-key',export_id='connected-test',issued_at_ns=b['snapshot'].origin_ns+1)
    result=run_session(s,enable_research=True,mode='connected',connected_profile=profile,connected_output=tmp_path/'export',export_metadata=metadata,sign_public_fixture=True)
    assert result['status']=='RESEARCH_PREDICTION' and result['prediction']['scale']>0
    assert result['provenance']['sources'][0]['engine']=='sqlite'
    assert result['mode']=='CONNECTED_SYNTHETIC_ENGINEERING_ONLY'

def test_verify_rejects_hash_pinned_invalid_checkpoint_and_report_escapes_labels(tmp_path):
    b,p,s=session(tmp_path)
    from dataclasses import replace
    from strattester.research.financial_session import verify_session,run_session
    from strattester.research.financial_report_export import export_report
    bad=tmp_path/'bad.json';bad.write_bytes(b'{}')
    bad_session=replace(s,request=replace(s.request,checkpoint_path=bad,checkpoint_sha256=sha256(b'{}').hexdigest()))
    with pytest.raises(ValueError):verify_session(bad_session)
    result=run_session(s,enable_research=True)
    result['prediction']['instrument']['symbol']='<script>alert(1)</script>'
    export_report(result,tmp_path/'escaped')
    html=(tmp_path/'escaped'/'report.html').read_text()
    assert '<script>' not in html and '&lt;script&gt;' in html

def test_native_connected_profile_blocks_before_database_and_unsigned_remains_unsigned(tmp_path,monkeypatch):
    b,p,s=session(tmp_path)
    from strattester.research.financial_session import run_session
    from strattester.research.financial_grid_exporter import HistoryProfile
    import sqlite3
    monkeypatch.setattr(sqlite3,'connect',lambda *a,**k:pytest.fail('database accessed'))
    with pytest.raises(RuntimeError,match='BLOCKED'):
        run_session(s,enable_research=True,mode='connected',connected_profile=HistoryProfile('NATIVE_GRID','epoch',1,()),connected_output=tmp_path/'export',export_metadata={})

def test_session_offline_actual_inference_has_no_network(tmp_path,monkeypatch):
    b,p,s=session(tmp_path)
    import socket
    monkeypatch.setattr(socket.socket,'connect',lambda *a,**k:pytest.fail('network accessed'))
    monkeypatch.setattr(socket,'create_connection',lambda *a,**k:pytest.fail('network accessed'))
    from strattester.research.financial_session import run_session
    assert run_session(s,enable_research=True)['status']=='RESEARCH_PREDICTION'

def test_disposable_cli_rejects_caller_selected_verification_clock():
    from strattester.research_cli import parser
    with pytest.raises(SystemExit):parser().parse_args(['test-disposable','--now-ns','1'])

def test_connected_profile_relative_database_uses_profile_directory_not_cwd(tmp_path):
    from strattester.research_cli import _profile
    from strattester.research.financial_snapshot import canonical_bytes
    folder=tmp_path/'package';folder.mkdir();(folder/'history.db').write_bytes(b'db')
    raw=dict(kind='SEALED_VERSIONED_HISTORY_V1',coherence_epoch_id='epoch',knowledge_cutoff_ns=1,scope='SYNTHETIC_ENGINEERING_ONLY',sources=[dict(source_id='one',engine='sqlite',location='history.db',snapshot_id='cut',seal_sha256='a'*64,partitions=[dict(exchange='bybit',market_type='linear',symbol='BTCUSDT',timeframe_ns=1)])])
    data=canonical_bytes(raw);path=folder/'profile.json';path.write_bytes(data)
    profile=_profile(path,sha256(data).hexdigest())
    assert profile.sources[0].location==str(folder/'history.db')
    raw['sources'][0]['location']='../history.db';data=canonical_bytes(raw);path.write_bytes(data)
    with pytest.raises(ValueError,match='path'):_profile(path,sha256(data).hexdigest())
