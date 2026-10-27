"""Explicit signed funding intake; signature authenticity is not historical truth.

No automatic runtime admission, networking, producer keys or Grid history repair.
Rates retain decimal bps; cashflows use the existing fixed-entry-notional contract.
"""
from dataclasses import dataclass, asdict, fields
from hashlib import sha256

from .financial_contract import Instrument, digest, integer
from .financial_funding import FundingEvent, FundingWindow
from .financial_snapshot import bounded_json, canonical_bytes, verified_bytes
from .financial_signatures import OpenSSLVerifier, load_trust_store, decode64, PUBLIC_SOFTWARE_FIXTURE_KEYS

FUNDING_DOMAIN = b'STRATTESTER_FUNDING_EXPORT_V1\x00'
_ENVELOPE = ('version', 'schema_sha256', 'producer_id', 'producer_build_sha', 'key_id',
    'source_id', 'source_schema_sha256', 'snapshot_id', 'coherence_epoch_id',
    'knowledge_cutoff_ns', 'issued_at_ns', 'scope', 'partition', 'start_ns', 'end_ns',
    'complete', 'first_availability_retained', 'revision_history_retained', 'events', 'signature_b64')
_EVENT = ('event_id', 'settlement_ns', 'available_ns', 'rate', 'rate_unit')
FUNDING_SCHEMA_SHA256 = sha256(canonical_bytes({'version': 1, 'envelope': _ENVELOPE,
    'event': _EVENT, 'partition': ('exchange', 'market_type', 'symbol', 'timeframe_ns'),
    'timestamp_unit': 'ns', 'rate_unit': 'decimal_bps', 'settlement_interval': '(entry,exit]'})).hexdigest()


def _identity(value):
    if type(value) is not str or not 1 <= len(value) <= 256 or value.strip() != value:
        raise ValueError('funding identity budget/type')


@dataclass(frozen=True)
class FundingPolicy:
    producer_id: str
    producer_build_sha: str
    source_id: str
    source_schema_sha256: str
    snapshot_id: str
    coherence_epoch_id: str
    instrument: Instrument
    timeframe_ns: int
    start_ns: int
    end_ns: int
    knowledge_cutoff_ns: int
    verification_ns: int
    scope: str = 'SYNTHETIC_ENGINEERING_ONLY'

    def validate(self):
        for name in ('producer_id', 'source_id', 'snapshot_id', 'coherence_epoch_id'):
            _identity(getattr(self, name))
        digest(self.producer_build_sha, 40); digest(self.source_schema_sha256)
        if type(self.instrument) is not Instrument:
            raise ValueError('funding instrument identity required')
        self.instrument.validate()
        for value in asdict(self.instrument).values():
            _identity(value)
            if '/' in value:
                raise ValueError('ambiguous funding ledger instrument separator')
        integer(self.timeframe_ns, 'funding timeframe', 1)
        for name in ('start_ns', 'end_ns', 'knowledge_cutoff_ns', 'verification_ns'):
            integer(getattr(self, name), name)
        if not self.start_ns < self.end_ns <= self.knowledge_cutoff_ns <= self.verification_ns:
            raise ValueError('funding coverage/cutoff policy')
        if self.scope not in ('SYNTHETIC_ENGINEERING_ONLY', 'PRODUCER_ATTESTED_RESEARCH'):
            raise ValueError('funding scope policy')
        return self


@dataclass(frozen=True)
class AuthenticatedFunding:
    window: FundingWindow
    provenance: dict


def load_funding_policy(path, expected_sha256):
    """Load policy only from independently pinned bounded bytes, never the export."""
    payload = bounded_json(verified_bytes(path, expected_sha256, 16 * 1024))
    if (set(payload) != {'version', *[f.name for f in fields(FundingPolicy)]}
            or type(payload['version']) is not int or payload['version'] != 1):
        raise ValueError('funding policy schema/version')
    try:
        policy = FundingPolicy(**{**{k: v for k, v in payload.items() if k != 'version'},
            'instrument': Instrument(**payload['instrument'])})
    except TypeError as exc:
        raise ValueError('funding policy instrument schema') from exc
    return policy.validate()


def load_authenticated_funding(*, path, expected_sha256, trust_store_path,
        trust_store_sha256, policy, verifier, cancel=lambda: False):
    """Verify externally pinned bytes under an independently provisioned trust policy.

    Caller supplies the producer cut, identity, coverage and trust pins. Returned
    coverage/history flags are signed assertions, never independent Grid evidence.
    """
    from .financial_training import TrainingCancelled
    def check():
        if cancel():
            raise TrainingCancelled('cancelled signed funding verification')
    check()
    if type(policy) is not FundingPolicy:
        raise ValueError('explicit funding policy required')
    policy.validate()
    if type(verifier) is not OpenSSLVerifier:
        raise ValueError('independent pinned funding verifier required')
    data = verified_bytes(path, expected_sha256, 1024 * 1024)
    manifest = bounded_json(data)
    if (set(manifest) != set(_ENVELOPE) or type(manifest['version']) is not int
            or manifest['version'] != 1 or manifest['schema_sha256'] != FUNDING_SCHEMA_SHA256):
        raise ValueError('funding schema/version mismatch')
    for name in ('producer_id', 'key_id', 'source_id', 'snapshot_id', 'coherence_epoch_id'):
        _identity(manifest[name])
    digest(manifest['producer_build_sha'], 40); digest(manifest['source_schema_sha256'])
    for name in ('knowledge_cutoff_ns', 'issued_at_ns', 'start_ns', 'end_ns'):
        integer(manifest[name], name)
    expected = {name: getattr(policy, name) for name in ('producer_id', 'producer_build_sha',
        'source_id', 'source_schema_sha256', 'snapshot_id', 'coherence_epoch_id',
        'knowledge_cutoff_ns', 'scope', 'start_ns', 'end_ns')}
    if canonical_bytes({name: manifest[name] for name in expected}) != canonical_bytes(expected):
        raise ValueError('funding source/epoch/coverage policy mismatch')
    partition = {**asdict(policy.instrument), 'timeframe_ns': policy.timeframe_ns}
    if canonical_bytes(manifest['partition']) != canonical_bytes(partition):
        raise ValueError('funding instrument/timeframe mismatch')
    if any(manifest[name] is not True for name in ('complete', 'first_availability_retained', 'revision_history_retained')):
        raise ValueError('BLOCKED: missing signed funding history/coverage assertions')
    if not policy.knowledge_cutoff_ns <= manifest['issued_at_ns'] <= policy.verification_ns:
        raise ValueError('funding issue time mismatch')
    if policy.verification_ns - manifest['issued_at_ns'] > 900_000_000_000:
        raise ValueError('stale funding issue time')
    rows = manifest['events']
    if type(rows) is not list or len(rows) > 10000:
        raise ValueError('funding event budget')
    instrument = '/'.join(asdict(policy.instrument).values())
    events = []
    for row in rows:
        check()
        if type(row) is not dict or set(row) != set(_EVENT):
            raise ValueError('funding event schema')
        events.append(FundingEvent(instrument=instrument, **row))
    window = FundingWindow(instrument, policy.start_ns, policy.end_ns,
        policy.knowledge_cutoff_ns, expected_sha256, tuple(events)).validate()
    trust = load_trust_store(trust_store_path, trust_store_sha256)
    key = trust.key(policy.producer_id, manifest['key_id'], manifest['issued_at_ns'])
    trust.key(policy.producer_id, manifest['key_id'], policy.verification_ns)
    if policy.scope == 'PRODUCER_ATTESTED_RESEARCH' and key in PUBLIC_SOFTWARE_FIXTURE_KEYS:
        raise ValueError('public fixture key cannot authenticate real funding producer')
    check()
    unsigned = {k: v for k, v in manifest.items() if k != 'signature_b64'}
    verifier.verify(key, FUNDING_DOMAIN + canonical_bytes(unsigned), decode64(manifest['signature_b64'], 64))
    check()
    return AuthenticatedFunding(window, {'manifest_sha256': expected_sha256,
        'policy_canonical_sha256': sha256(canonical_bytes({'version': 1, **asdict(policy)})).hexdigest(),
        'schema_sha256': FUNDING_SCHEMA_SHA256, 'signature_verifier_sha256': verifier.executable_sha256,
        'key_id': manifest['key_id'],
        'trust_store_sha256': trust_store_sha256, 'producer_id': policy.producer_id,
        'producer_build_sha': policy.producer_build_sha, 'source_id': policy.source_id,
        'source_schema_sha256': policy.source_schema_sha256, 'snapshot_id': policy.snapshot_id,
        'coherence_epoch_id': policy.coherence_epoch_id, 'partition': partition,
        'knowledge_cutoff_ns': policy.knowledge_cutoff_ns, 'issued_at_ns': manifest['issued_at_ns'],
        'verification_ns': policy.verification_ns, 'scope': policy.scope, 'event_count': len(events),
        'authentication': 'PINNED_ED25519_BYTES_VERIFIED',
        'historical_truth': 'NOT_ESTABLISHED_BY_SIGNATURE',
        'runtime_funding_admission': 'NOT_ENABLED', 'physical_g1': 'NOT_AUTHORIZED', 'trading': 'NO-GO'})
