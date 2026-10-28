from hashlib import sha256
from pathlib import Path
import json
import pytest

def payload():
    return dict(version=2,purpose='PHYSICAL_G1_AUTHORIZATION',owner_id='test-owner',key_id='key',
        target_sha='a'*40,tree_sha='b'*40,binary_sha256='c'*64,package_sha256='d'*64,
        vm_identity_sha256='e'*64,input_hashes={'snapshot':'f'*64,'package':'d'*64},issued_at_ns=100,expires_at_ns=200,
        nonce='1'*64,operations=['synthetic_cpu_inference'],limits=dict(cpu_percent=10,memory_bytes=2147483648,wall_seconds=60,output_bytes=67108864,max_processes=1))

def test_v2_binds_every_input_and_vm_without_authorizing_g1():
    from strattester.research.financial_owner_intent_v2 import canonical_owner_intent
    p=payload();encoded=canonical_owner_intent(p,now_ns=150)
    assert json.loads(encoded)==p
    assert encoded==json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()

@pytest.mark.parametrize('field,value',[('version',1),('vm_identity_sha256','bad'),('input_hashes',{}),
    ('input_hashes',{'../escape':'f'*64}),('expires_at_ns',99),('issued_at_ns',151),
    ('owner_id','é'),('nonce','x'*64),('operations',['trade']),('expires_at_ns',10**30)])
def test_v2_rejects_ambiguous_or_incompatible_fields(field,value):
    from strattester.research.financial_owner_intent_v2 import canonical_owner_intent
    p=payload();p[field]=value
    with pytest.raises(ValueError):canonical_owner_intent(p,now_ns=150)

def test_v2_rejects_extra_keys_boolean_limits_and_excess_input_budget():
    from strattester.research.financial_owner_intent_v2 import canonical_owner_intent
    p=payload();p['extra']=0
    with pytest.raises(ValueError):canonical_owner_intent(p,now_ns=150)
    p=payload();p['limits']['cpu_percent']=True
    with pytest.raises(ValueError):canonical_owner_intent(p,now_ns=150)
    p=payload();p['input_hashes']={str(i):'f'*64 for i in range(65)}
    with pytest.raises(ValueError):canonical_owner_intent(p,now_ns=150)


@pytest.mark.parametrize('field', ['cpu_percent','memory_bytes','wall_seconds','output_bytes','max_processes'])
@pytest.mark.parametrize('invalid', ['zero','boolean','above_cap'])
def test_every_owner_resource_ceiling_fails_closed(field, invalid):
    from strattester.research.financial_owner_intent_v2 import canonical_owner_intent, CAPS
    p=payload()
    p['limits'][field]={'zero':0,'boolean':True,'above_cap':CAPS[field]+1}[invalid]
    with pytest.raises(ValueError):canonical_owner_intent(p,now_ns=150)


def test_owner_exact_expiry_and_input_hash_bounds():
    from strattester.research.financial_owner_intent_v2 import canonical_owner_intent
    p=payload()
    assert canonical_owner_intent(p,now_ns=200)
    with pytest.raises(ValueError):canonical_owner_intent(p,now_ns=201)
    p['expires_at_ns']=p['issued_at_ns']+600_000_000_001
    with pytest.raises(ValueError):canonical_owner_intent(p,now_ns=150)
    p=payload();p['input_hashes']['package']='0'*64
    with pytest.raises(ValueError):canonical_owner_intent(p,now_ns=150)
