"""Readonly proposed bundle integrity, never receipt authentication/admission."""
import re
from pathlib import Path
from .adapter import _read, _hex, _json, _digest
from .native_inspect import inspect_grid_v11


def inspect_snapshot_bundle(snapshot_path, snapshot_sha256, source_head,
                            manifest_path, manifest_sha256):
    """Inspect explicitly supplied local files, without scanning or fetching.

    Sidecar format is a local proposal. Verified bytes cannot authenticate the
    source owner or grant native admission. No conversion to trainable bars.
    """
    _hex(manifest_sha256, 64)
    raw = _read(manifest_path)
    if len(raw) > 65536 or _digest(raw) != manifest_sha256:
        raise ValueError('MANIFEST_RAW_PIN')
    manifest = _json(raw)
    keys = {'schema', 'dataset_id', 'dataset_fingerprint', 'source_head',
            'snapshot_sha256', 'references'}
    if type(manifest) is not dict or set(manifest) != keys:
        raise ValueError('MANIFEST_SCHEMA')
    if manifest['schema'] != 'mwi.snapshot.bundle.PROPOSAL.v1':
        raise ValueError('MANIFEST_VERSION')
    inspection = inspect_grid_v11(snapshot_path, snapshot_sha256, source_head)
    expected = dict(dataset_id=inspection['dataset_id'],
                    dataset_fingerprint=inspection['dataset_fingerprint'],
                    source_head=source_head, snapshot_sha256=snapshot_sha256)
    if any(type(manifest[k]) is not str or manifest[k] != v for k, v in expected.items()):
        raise ValueError('MANIFEST_IDENTITY_BINDING')
    refs = manifest['references']
    names = {'source_provenance', 'source_owner_approval', 'external_artifact_admission'}
    if type(refs) is not dict or set(refs) != names:
        raise ValueError('REFERENCE_SCHEMA')
    integrity = {}
    for key in sorted(names):
        ref = refs[key]
        if ref is None:
            integrity[key] = 'NOT_PROVIDED'
            continue
        if type(ref) is not dict or set(ref) != {'file', 'sha256', 'bytes'}:
            raise ValueError('REFERENCE_SCHEMA')
        name = ref['file']
        if type(name) is not str or re.fullmatch(r'[A-Za-z0-9_-]{1,80}\.json', name) is None:
            raise ValueError('REFERENCE_LOCAL_BASENAME')
        _hex(ref['sha256'], 64)
        if type(ref['bytes']) is not int or not 1 <= ref['bytes'] <= 65536:
            raise ValueError('REFERENCE_BYTE_BUDGET')
        evidence = _read(Path(manifest_path).absolute().parent/name)
        if len(evidence) != ref['bytes'] or _digest(evidence) != ref['sha256']:
            raise ValueError('REFERENCE_RAW_PIN')
        integrity[key] = 'HASH_VERIFIED_NOT_AUTHENTICATED'
    return dict(schema='mwi.snapshot.readiness.PROPOSAL.v1',
                status='REAL_DATA_TRAINING_BLOCKED', training_eligible=False,
                inspection=inspection, manifest_sha256=manifest_sha256,
                reference_integrity=integrity,
                missingness=dict(ohlcv_gap_count=inspection['coverage']['gaps'],
                                 other_modalities='UNKNOWN_NOT_IN_THIS_ARTIFACT'),
                feature_coverage=dict(ohlcv='PRESENT_IN_INSPECTED_FILE', l2='UNKNOWN',
                                      trades='UNKNOWN', footprint='UNKNOWN', oi='UNKNOWN', funding='UNKNOWN'),
                blockers=['OWNER_ADMISSION_VERIFIER_NOT_PROVISIONED',
                          'SOURCE_AUTHENTICATION_NOT_PROVISIONED',
                          'ACTUAL_FEATURE_COVERAGE_NOT_QUALIFIED',
                          'NATIVE_TRAINING_ADMISSION_NOT_IMPLEMENTED'])
