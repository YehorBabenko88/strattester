"""Opt-in, offline-only financial structural inference boundary.

Does not use ResearchRunner, SyncEngine, registry auto-discovery or live stores.
Caller must provide pinned, trusted artifacts and a prevalidated market identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from .financial_contract import Instrument, integer, digest
from .financial_snapshot import load_snapshot
from .financial_checkpoint import load_checkpoint
from .financial_pipeline import predict_snapshot


@dataclass(frozen=True)
class OfflineInferenceRequest:
    snapshot_path: Path
    snapshot_sha256: str
    checkpoint_path: Path
    checkpoint_sha256: str
    producer_ids: frozenset[str]
    coherence_id: str
    instrument: Instrument
    timeframe_ns: int
    horizon_ns: int
    available_ns: int

    def validate(self):
        digest(self.snapshot_sha256)
        digest(self.checkpoint_sha256)
        self.instrument.validate()
        for name in ("timeframe_ns", "horizon_ns", "available_ns"):
            integer(getattr(self, name), name, 1)
        if (type(self.producer_ids) is not frozenset
                or not self.producer_ids
                or any(not isinstance(x, str) or not x for x in self.producer_ids)
                or not isinstance(self.coherence_id, str) or not self.coherence_id):
            raise ValueError("explicit trusted producer/coherence required")
        if not Path(self.snapshot_path).is_file() or not Path(self.checkpoint_path).is_file():
            raise ValueError("missing offline artifacts")
        return self


def run_verified_offline(request: OfflineInferenceRequest):
    """Return one typed prediction. No network, database or trading operations."""
    request.validate()
    snapshot = load_snapshot(
        request.snapshot_path, request.snapshot_sha256,
        trusted_producers=request.producer_ids,
        expected_coherence=request.coherence_id,
    )
    if request.available_ns < snapshot.origin_ns:
        raise ValueError("prediction cannot be available before origin")
    model, metadata = load_checkpoint(
        request.checkpoint_path, request.checkpoint_sha256,
    )
    if request.horizon_ns != model.config.horizon_ns:
        raise ValueError("checkpoint horizon mismatch")
    prediction = predict_snapshot(
        snapshot, model, instrument=request.instrument,
        timeframe_ns=request.timeframe_ns,
        horizon_ns=request.horizon_ns,
        model_sha256=request.checkpoint_sha256,
        available_ns=request.available_ns,
    )
    return prediction
