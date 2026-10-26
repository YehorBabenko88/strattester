"""Public software-fixture authority must not authenticate real research."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import json
import runpy
import pytest
from strattester.research.financial_snapshot import canonical_bytes, snapshot_bytes


@pytest.mark.parametrize('alias', [False, True])
def test_public_fixture_key_cannot_authenticate_real_research_even_with_relabelled_ids(tmp_path, alias):
    from strattester.research.financial_signed_export import load_attested_export
    bundle = runpy.run_path(str(Path(__file__).with_name('signed_export_fixture.py')))['bundle'](tmp_path)
    manifest = bundle['manifest']
    producer = 'producer-renamed' if alias else manifest['producer_id']
    key_id = 'key-renamed' if alias else manifest['key_id']
    source = replace(bundle['policy'].sources[0], engine='postgresql')
    policy = replace(bundle['policy'], producer_id=producer, sources=(source,), scope='PRODUCER_ATTESTED_RESEARCH')
    manifest.update(producer_id=producer, key_id=key_id, scope=policy.scope)
    manifest['sources'][0]['engine'] = source.engine
    snapshot = replace(bundle['snapshot'], producers=(producer,), bars=tuple(replace(b, producer=producer) for b in bundle['snapshot'].bars))
    data = snapshot_bytes(snapshot)
    (tmp_path/'snapshot.json').write_bytes(data)
    manifest.update(snapshot_sha256=sha256(data).hexdigest(), snapshot_bytes=len(data))
    trust = json.loads((tmp_path/'trust.json').read_bytes())
    trust['keys'][0].update(producer_id=producer, key_id=key_id)
    trust_data = canonical_bytes(trust)
    (tmp_path/'trust.json').write_bytes(trust_data)
    pin = bundle['publish'](manifest)  # Genuine Ed25519 signature using the shipped public fixture key.
    with pytest.raises(ValueError, match='public fixture'):
        load_attested_export(manifest_path=tmp_path/'manifest.json', manifest_sha256=pin,
            snapshot_path=tmp_path/'snapshot.json', trust_store_path=tmp_path/'trust.json',
            trust_store_sha256=sha256(trust_data).hexdigest(), policy=policy, verifier=bundle['verifier'])
