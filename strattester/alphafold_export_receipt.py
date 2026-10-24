"""Strict consumer-side verification of a producer-issued export receipt.

A digest is not an attestation. This verifier deliberately requires a trusted
signature callback supplied by the deployment's independently configured trust
store; no self-signed or unsigned receipts are accepted.
"""
from __future__ import annotations
from collections.abc import Callable, Mapping
from hashlib import sha256
import json


class ExportReceiptError(ValueError):
    pass


REQUIRED = frozenset({
    "protocol_version", "producer_id", "export_id", "coherence_epoch_id",
    "source_id", "schema_version", "market_identity", "knowledge_cutoff_ns",
    "event_watermark_ns", "availability_watermark_ns", "row_count",
    "artifact_sha256", "artifact_bytes", "signing_key_id", "signature",
})


def canonical_receipt_bytes(receipt: Mapping) -> bytes:
    """Canonical unsigned JSON envelope; reject NaN and unsupported values."""
    payload = {key: value for key, value in receipt.items() if key != "signature"}
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ExportReceiptError("Invalid receipt encoding") from exc


def verify_export_receipt(
    receipt: Mapping,
    artifact: bytes,
    *,
    expected_producer: str,
    expected_source: str,
    expected_epoch: str,
    expected_market_identity: Mapping,
    knowledge_cutoff_ns: int,
    max_artifact_bytes: int,
    verify_signature: Callable[[str, bytes, str], bool],
) -> None:
    if type(receipt) is not dict or set(receipt) != REQUIRED:
        raise ExportReceiptError("Unexpected receipt schema")
    if receipt["protocol_version"] != 1:
        raise ExportReceiptError("Unsupported receipt protocol")
    for field, expected in (
        ("producer_id", expected_producer), ("source_id", expected_source),
        ("coherence_epoch_id", expected_epoch),
        ("market_identity", expected_market_identity),
        ("knowledge_cutoff_ns", knowledge_cutoff_ns),
    ):
        if receipt[field] != expected:
            raise ExportReceiptError(f"Receipt {field} mismatch")
    for field in ("producer_id", "source_id", "export_id",
                  "coherence_epoch_id", "schema_version", "signing_key_id",
                  "signature"):
        if type(receipt[field]) is not str or not receipt[field]:
            raise ExportReceiptError(f"Invalid {field}")
    for field in ("knowledge_cutoff_ns", "event_watermark_ns",
                  "availability_watermark_ns", "row_count", "artifact_bytes"):
        if type(receipt[field]) is not int or receipt[field] < 0:
            raise ExportReceiptError(f"Invalid {field}")
    if (type(knowledge_cutoff_ns) is not int or knowledge_cutoff_ns < 0
            or type(max_artifact_bytes) is not int or max_artifact_bytes < 1):
        raise ExportReceiptError("Invalid caller limits")
    if receipt["event_watermark_ns"] < knowledge_cutoff_ns:
        raise ExportReceiptError("Event watermark insufficient")
    if receipt["availability_watermark_ns"] < knowledge_cutoff_ns:
        raise ExportReceiptError("Availability watermark insufficient")
    if (type(artifact) is not bytes or len(artifact) > max_artifact_bytes
            or len(artifact) != receipt["artifact_bytes"]):
        raise ExportReceiptError("Artifact byte budget/size mismatch")
    expected_hash = receipt["artifact_sha256"]
    if (type(expected_hash) is not str or len(expected_hash) != 64
            or any(c not in "0123456789abcdef" for c in expected_hash)
            or sha256(artifact).hexdigest() != expected_hash):
        raise ExportReceiptError("Artifact SHA256 mismatch")
    if not verify_signature(
        receipt["signing_key_id"], canonical_receipt_bytes(receipt),
        receipt["signature"]
    ):
        raise ExportReceiptError("Untrusted producer signature")
