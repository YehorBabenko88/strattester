import pytest
from research.independent_provenance_oracle import canonical_provenance

def fixture():
    return dict(producer_repo='YehorBabenko88/bybit-cluster-grid',producer_commit='a'*40,consumer_commit='b'*40,schema_version='v1',snapshot_sha256='c'*64,time_unit='ns',price_unit='USDT',feature_version='v1')

def test_canonical_digest_order_invariance():
    a=fixture()
    assert canonical_provenance(a)==canonical_provenance(dict(reversed(list(a.items()))))

def test_tamper_and_ambiguous_units():
    a=fixture()
    original=canonical_provenance(a)
    a['feature_version']='v2'
    assert canonical_provenance(a)!=original
    a['time_unit']='ms'
    with pytest.raises(ValueError):
        canonical_provenance(a)

def test_missing_commit_and_hash_fail_closed():
    a=fixture()
    a['producer_commit']='not-a-sha'
    with pytest.raises(ValueError):
        canonical_provenance(a)
