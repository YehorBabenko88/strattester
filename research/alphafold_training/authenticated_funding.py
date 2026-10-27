"""Authenticated offline funding input contract.

Authentication requires an independently trusted HMAC key and canonical bytes.
A self-declared hash or unsigned JSON is NOT authenticated evidence.
No network, credentials, production DB or live execution.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import math

@dataclass(frozen=True)
class FundingRecord:
    instrument: str
    event_ns: int
    available_ns: int
    rate: float

def canonical_funding(records, *, producer, epoch, dataset_version):
    if not all(isinstance(v, str) and v.strip() and v == v.strip()
               for v in (producer, epoch, dataset_version)):
        raise ValueError("missing producer identity")
    rows = list(records)
    if not rows:
        raise ValueError("empty funding dataset")
    seen = set()
    result = []
    for r in rows:
        if not isinstance(r, FundingRecord) or not isinstance(r.instrument, str) or not r.instrument:
            raise ValueError("invalid funding record")
        if any(type(t) is not int or t < 0 for t in (r.event_ns, r.available_ns)):
            raise ValueError("invalid funding timestamp")
        if r.available_ns < r.event_ns:
            raise ValueError("funding availability precedes event")
        if type(r.rate) not in (int, float) or not math.isfinite(r.rate):
            raise ValueError("invalid funding rate")
        key = (r.instrument, r.event_ns)
        if key in seen:
            raise ValueError("duplicate funding event")
        seen.add(key)
        result.append({"instrument": r.instrument, "event_ns": r.event_ns,
                       "available_ns": r.available_ns, "rate": r.rate})
    result.sort(key=lambda x: (x["event_ns"], x["instrument"]))
    return json.dumps({"schema": "funding.auth.v1", "producer": producer,
                       "epoch": epoch, "dataset_version": dataset_version,
                       "records": result}, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")

def verify_funding(records, *, producer, epoch, dataset_version, trusted_key, expected_mac):
    if not isinstance(trusted_key, bytes) or len(trusted_key) < 32:
        raise ValueError("external trusted key required")
    if not isinstance(expected_mac, str) or len(expected_mac) != 64:
        raise ValueError("invalid expected MAC")
    data = canonical_funding(records, producer=producer, epoch=epoch,
                             dataset_version=dataset_version)
    computed = hmac.new(trusted_key, data, sha256).hexdigest()
    if not hmac.compare_digest(computed, expected_mac):
        raise ValueError("funding authentication failed")
    return {"status": "AUTHENTICATED_OFFLINE_INPUT", "sha256": sha256(data).hexdigest(),
            "count": len(json.loads(data)["records"]), "producer": producer, "epoch": epoch}
