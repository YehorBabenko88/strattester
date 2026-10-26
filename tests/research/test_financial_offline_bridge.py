from pathlib import Path
import pytest

from strattester.research.financial_contract import Instrument
from strattester.research.financial_offline_bridge import (
    OfflineInferenceRequest, run_verified_offline,
)

SHA = "a" * 64


def request(tmp_path, **changes):
    values = dict(
        snapshot_path=tmp_path / "snapshot.json",
        snapshot_sha256=SHA,
        checkpoint_path=tmp_path / "checkpoint.json",
        checkpoint_sha256=SHA,
        producer_ids=frozenset({"trusted-grid"}),
        coherence_id="epoch-test",
        instrument=Instrument("bybit", "linear", "BTCUSDT"),
        timeframe_ns=60_000_000_000,
        horizon_ns=120_000_000_000,
        available_ns=300_000_000_000,
    )
    values.update(changes)
    return OfflineInferenceRequest(**values)


def test_missing_files_fail_closed(tmp_path):
    with pytest.raises(ValueError, match="missing offline artifacts"):
        run_verified_offline(request(tmp_path))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("changes", [
    {"producer_ids": frozenset()},
    {"coherence_id": ""},
    {"timeframe_ns": 0},
    {"horizon_ns": 0},
    {"available_ns": 0},
    {"snapshot_sha256": "invalid"},
])
def test_invalid_request_rejected_before_artifact_load(tmp_path, changes):
    with pytest.raises(ValueError):
        request(tmp_path, **changes).validate()


def test_reject_forged_snapshot_bytes(tmp_path):
    (tmp_path / "snapshot.json").write_bytes(b"{}")
    (tmp_path / "checkpoint.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        run_verified_offline(request(tmp_path))
