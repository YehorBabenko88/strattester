"""Opt-in offline research dispatch with explicit strategy and side-effect gates.

Do not use this for live trading. Only a typed financial Snapshot is accepted.
"""
from __future__ import annotations
from strattester.research.financial_contract import Snapshot, Instrument, integer, digest
from strattester.research.financial_checkpoint import load_checkpoint
from strattester.research.financial_pipeline import predict_snapshot
from strattester.research.financial_research_spec import FinancialResearchSpec

def predict_research_only(spec, snapshot, *, instrument, model_path, model_sha256,
                          timeframe_ns, horizon_ns, available_ns):
    """Load a trusted tensor-only checkpoint and predict from verified offline snapshot.

    No order client, exchange credentials, database handle or live strategy context
    is accepted by this API. Artifact loading is digest-pinned.
    """
    if type(spec) is not FinancialResearchSpec:
        raise ValueError("explicit financial research specification required")
    spec.validate()
    if type(snapshot) is not Snapshot:
        raise ValueError("typed verified Snapshot required")
    snapshot.validate()
    if type(instrument) is not Instrument or instrument not in spec.universe:
        raise ValueError("target outside authorized research universe")
    if any(bar.instrument not in spec.universe for bar in snapshot.bars):
        raise ValueError("snapshot context outside authorized universe")
    if any(bar.timeframe_ns != spec.timeframe_ns for bar in snapshot.bars):
        raise ValueError("snapshot contains unapproved cross-timeframe context")
    if not any(bar.instrument == instrument and bar.timeframe_ns == spec.timeframe_ns for bar in snapshot.bars):
        raise ValueError("target/timeframe absent from verified snapshot")
    if timeframe_ns != spec.timeframe_ns or horizon_ns != spec.forecast_horizon_ns:
        raise ValueError("timeframe/horizon differs from frozen research specification")
    integer(available_ns, "prediction available_ns")
    digest(model_sha256)
    # Reject backdated availability before reading any checkpoint bytes.
    if available_ns < snapshot.origin_ns:
        raise ValueError("prediction availability predates snapshot")
    model, metadata = load_checkpoint(model_path, model_sha256)
    if model.config.horizon_ns != spec.forecast_horizon_ns:
        raise ValueError("checkpoint horizon mismatch")
    if (not isinstance(metadata, dict) or not isinstance(metadata.get("config"), dict)
            or metadata["config"].get("horizon_ns") != spec.forecast_horizon_ns):
        raise ValueError("checkpoint metadata horizon mismatch")
    return predict_snapshot(snapshot, model, instrument=instrument,
                            timeframe_ns=timeframe_ns, horizon_ns=horizon_ns,
                            model_sha256=model_sha256, available_ns=available_ns)
