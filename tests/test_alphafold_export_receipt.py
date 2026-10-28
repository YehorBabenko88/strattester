from hashlib import sha256
import pytest

from strattester.alphafold_export_receipt import (
    ExportReceiptError, canonical_receipt_bytes, verify_export_receipt,
)


ARTIFACT = b"immutable synthetic export"


def receipt():
    return dict(
        protocol_version=1, producer_id="grid-fixture",
        export_id="export-1", coherence_epoch_id="epoch-1",
        source_id="shard-1", schema_version="fixture-v1",
        market_identity={"exchange": "bybit", "market_type": "linear",
                         "symbol": "BTCUSDT", "timeframe_ns": 60_000_000_000},
        knowledge_cutoff_ns=100, event_watermark_ns=100,
        availability_watermark_ns=100, row_count=1,
        artifact_sha256=sha256(ARTIFACT).hexdigest(),
        artifact_bytes=len(ARTIFACT), signing_key_id="fixture-key",
        signature="fixture-signature",
    )


def check(data, artifact=ARTIFACT, verifier=None):
    return verify_export_receipt(
        data, artifact, expected_producer="grid-fixture",
        expected_source="shard-1", expected_epoch="epoch-1",
        expected_market_identity=receipt()["market_identity"],
        knowledge_cutoff_ns=100, max_artifact_bytes=1024,
        verify_signature=verifier or (lambda key, message, signature: False),
    )


def test_trusted_callback_receives_exact_unsigned_bytes():
    data = receipt()
    def trusted(key, message, signature):
        return key == "fixture-key" and signature == "fixture-signature" and message == canonical_receipt_bytes(data)
    check(data, verifier=trusted)


def test_untrusted_signature_rejected():
    with pytest.raises(ExportReceiptError, match="signature"):
        check(receipt())


@pytest.mark.parametrize("field,value", [
    ("source_id", "unexpected"), ("coherence_epoch_id", "other"),
    ("knowledge_cutoff_ns", 101), ("event_watermark_ns", 99),
    ("availability_watermark_ns", 99), ("row_count", True),
    ("artifact_sha256", "0" * 64), ("artifact_bytes", 2),
])
def test_receipt_tampering_rejected(field, value):
    data = receipt()
    data[field] = value
    with pytest.raises(ExportReceiptError):
        check(data, verifier=lambda *args: True)


def test_artifact_tampering_rejected():
    with pytest.raises(ExportReceiptError, match="SHA256"):
        check(receipt(), artifact=b"x" * len(ARTIFACT),
              verifier=lambda *args: True)


def test_extra_field_rejected():
    data = receipt()
    data["fake_history"] = True
    with pytest.raises(ExportReceiptError, match="schema"):
        check(data, verifier=lambda *args: True)
