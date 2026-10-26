import runpy
from pathlib import Path
from dataclasses import replace
import pytest

def fixture(tmp_path,**kwargs):
    return runpy.run_path(str(Path(__file__).with_name('signed_export_fixture.py')))['bundle'](tmp_path,**kwargs)

def load(b,**changes):
    from strattester.research.financial_signed_export import load_attested_export
    args=dict(manifest_path=b['root']/'manifest.json',manifest_sha256=b['manifest_sha'],snapshot_path=b['root']/'snapshot.json',trust_store_path=b['root']/'trust.json',trust_store_sha256=b['trust_sha'],policy=b['policy'],verifier=b['verifier'])
    args.update(changes);return load_attested_export(**args)


def test_real_signature_to_immutable_typed_snapshot(tmp_path):
    b=fixture(tmp_path);verified=load(b)
    assert verified.snapshot==b['snapshot']
    assert verified.provenance['manifest_sha256']==b['manifest_sha']
    assert verified.provenance['trust_store_sha256']==b['trust_sha']
    assert verified.provenance['scope']=='SYNTHETIC_ENGINEERING_ONLY'

@pytest.mark.parametrize('field,value',[('coherence_epoch_id','replayed'),('producer_id','attacker'),('snapshot_schema_version',True),('snapshot_schema_sha256','0'*64),('row_count',99),('knowledge_cutoff_ns',1),('partitions',[]),('sources',[])])
def test_signed_but_policy_incompatible_manifest_rejected(tmp_path,field,value):
    b=fixture(tmp_path);b['manifest'][field]=value;b['manifest_sha']=b['publish'](b['manifest'])
    with pytest.raises(ValueError):load(b)


def test_snapshot_changed_after_manifest_signing_rejected(tmp_path):
    b=fixture(tmp_path);(tmp_path/'snapshot.json').write_bytes(b'{}')
    with pytest.raises(ValueError):load(b)


def test_trust_store_cannot_be_replaced_with_artifact_selected_key(tmp_path):
    b=fixture(tmp_path);(tmp_path/'trust.json').write_bytes(b'{}')
    with pytest.raises(ValueError):load(b)


def test_signed_missing_historical_facts_never_become_verified(tmp_path):
    b=fixture(tmp_path);b['manifest']['sources'][0]['first_availability_retained']=False;b['manifest_sha']=b['publish'](b['manifest'])
    with pytest.raises(ValueError):load(b)


def test_signed_fixture_cannot_relabel_itself_as_real_research(tmp_path):
    b=fixture(tmp_path);b['manifest']['scope']='PRODUCER_ATTESTED_RESEARCH';b['manifest_sha']=b['publish'](b['manifest'])
    with pytest.raises(ValueError,match='scope'):load(b)


def test_export_key_validity_is_checked_at_verification_not_market_cutoff(tmp_path):
    import json
    from hashlib import sha256
    from strattester.research.financial_snapshot import canonical_bytes
    b=fixture(tmp_path);p=tmp_path/'trust.json';trust=json.loads(p.read_bytes())
    trust['keys'][0]['valid_until_ns']=b['snapshot'].origin_ns
    data=canonical_bytes(trust);p.write_bytes(data);b['trust_sha']=sha256(data).hexdigest()
    with pytest.raises(ValueError,match='expired'):load(b)
