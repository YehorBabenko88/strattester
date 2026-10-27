"""Trusted manifest binding for offline funding coverage.

Manifest authentication uses an externally pinned HMAC key. This does not
establish truth of exchange history without independent producer qualification.
"""
import hashlib
import hmac
import json

def verify_coverage_manifest(manifest, *, trusted_key, expected_mac, funding_sha256):
    if type(manifest) is not dict or set(manifest) != {
        "schema", "producer", "epoch", "dataset_version", "funding_sha256",
        "coverage_start_ns", "coverage_end_ns", "instruments", "complete"
    }:
        raise ValueError("invalid coverage manifest schema")
    if manifest["schema"] != "funding.coverage.v1" or type(manifest["complete"]) is not bool or not manifest["complete"]:
        raise ValueError("producer coverage not complete")
    if any(type(manifest[k]) is not str or not manifest[k] for k in ("producer", "epoch", "dataset_version")):
        raise ValueError("invalid producer identity")
    if type(manifest["coverage_start_ns"]) is not int or type(manifest["coverage_end_ns"]) is not int or not 0 <= manifest["coverage_start_ns"] < manifest["coverage_end_ns"]:
        raise ValueError("invalid coverage interval")
    if (type(manifest["instruments"]) is not list or not manifest["instruments"]
            or any(type(x) is not str or not x for x in manifest["instruments"])
            or len(set(manifest["instruments"])) != len(manifest["instruments"])):
        raise ValueError("invalid coverage universe")
    if manifest["funding_sha256"] != funding_sha256:
        raise ValueError("funding snapshot digest mismatch")
    if type(trusted_key) is not bytes or len(trusted_key) < 32 or type(expected_mac) is not str or len(expected_mac) != 64:
        raise ValueError("independent trust anchor required")
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    mac = hmac.new(trusted_key, payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected_mac):
        raise ValueError("coverage manifest authentication failed")
    return {"status": "AUTHENTICATED_PRODUCER_ASSERTION",
            "manifest_sha256": hashlib.sha256(payload).hexdigest(),
            "coverage_start_ns": manifest["coverage_start_ns"],
            "coverage_end_ns": manifest["coverage_end_ns"],
            "instruments": tuple(manifest["instruments"])}
