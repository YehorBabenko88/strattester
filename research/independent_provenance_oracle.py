"""Pure source provenance and mathematical fixture attestation."""
import hashlib
import json

REQUIRED = ('producer_repo','producer_commit','consumer_commit','schema_version','snapshot_sha256','time_unit','price_unit','feature_version')

def canonical_provenance(record):
    if not isinstance(record,dict) or any(key not in record for key in REQUIRED):
        raise ValueError("missing provenance")
    if any(not isinstance(record[k],str) or not record[k] for k in REQUIRED):
        raise ValueError("invalid provenance")
    if record['time_unit'] != 'ns':
        raise ValueError("ambiguous timestamp units")
    for key in ('producer_commit','consumer_commit','snapshot_sha256'):
        value = record[key]
        if len(value) != (64 if key == 'snapshot_sha256' else 40) or any(c not in '0123456789abcdef' for c in value):
            raise ValueError("invalid provenance digest")
    encoded = json.dumps({k:record[k] for k in sorted(REQUIRED)},sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')
    return hashlib.sha256(encoded).hexdigest()
