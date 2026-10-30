"""Bounded read-only bridge from independently reviewed history to scientific UI.

This is a display handoff, NOT a Math v2.1 executable source or market admission.
Event timestamps and first availability deliberately remain separate.
"""
from .grid_math_history import canonical, digest, number

SCHEMA = "terminan.history.scientific-handoff.v1"


def handoff_packet(review):
    if type(review) is not dict or len(canonical(review)) > 8 * 1024 * 1024:
        raise ValueError("HANDOFF_LIMIT")
    if review.get("schema") != "terminan.history.review.v1.1":
        raise ValueError("REVIEW_SCHEMA")
    receipt = review.get("packet_fingerprint")
    if type(receipt) is not str or len(receipt) != 64 or digest({
        k: v for k, v in review.items() if k != "packet_fingerprint"
    }) != receipt:
        raise ValueError("REVIEW_FINGERPRINT")
    if any(review.get(k) is not False for k in
           ("training_authorized", "trading_authorized", "execution_authority")):
        raise ValueError("AUTHORITY")
    src = review.get("source")
    if (type(src) is not dict or
        src.get("source_authenticity") != "REQUIRES_INDEPENDENT_RECEIPT_PROVISIONING" or
        review.get("evidence_class") != "SYNTHETIC"):
        raise ValueError("SOURCE_NOT_ADMITTED")
    rows = review.get("observations")
    if type(rows) is not list or not 1 <= len(rows) <= 2000:
        raise ValueError("OBSERVATION_COUNT")
    prices = []
    prev_end = -1
    for row in rows:
        if type(row) is not dict:
            raise ValueError("OBSERVATION")
        ts, available, watermark = (row.get(k) for k in
                                    ("event_end_ms", "available_at_ms", "watermark_ms"))
        if (any(type(v) is not int or v < 0 or v > 2**53-1 for v in
                (ts, available, watermark)) or
            not prev_end < ts <= watermark <= available or
            not number(row.get("close")) or row["close"] <= 0):
            raise ValueError("HISTORY_CLOCK")
        prices.append({"event_end_ms": ts, "available_at_ms": available,
                       "watermark_ms": watermark, "value": row["close"]})
        prev_end = ts
    traces = review.get("math_trace")
    if type(traces) is not list or len(traces) > 2000:
        raise ValueError("TRACE_LIMIT")
    forecasts = []
    for t in traces:
        if type(t) is not dict:
            raise ValueError("TRACE")
        event, known, target = (t.get(k) for k in
            ("feature_event_end_ms", "feature_available_at_ms",
             "forecast_target_event_end_ms"))
        decision = t.get("decision_ms")
        if (any(type(x) is not int for x in (event, known, target, decision))
            or not 0 <= event <= known <= decision < target
            or not number(t.get("forecast")) or t["forecast"] <= 0
            or type(t.get("request_digest")) is not str
            or len(t["request_digest"]) != 64
            or any(c not in "0123456789abcdef" for c in t["request_digest"])):
            raise ValueError("TRACE_CHRONOLOGY")
        forecasts.append({"feature_event_end_ms": event,
                          "feature_available_at_ms": known, "decision_ms": decision,
                          "target_event_end_ms": target, "value": t["forecast"],
                          "request_digest": t["request_digest"]})
    packet = {"schema": SCHEMA, "origin_schema": review["schema"],
              "review_fingerprint": receipt, "result_receipt": review["result_receipt"],
              "dataset_id": src["dataset_id"],
              "snapshot_fingerprint": src["snapshot_fingerprint"],
              "source": src, "market": src["identity"], "strategy": review["strategy"],
              "evidence_class": "SYNTHETIC",
              "source_authenticity": "UNATTESTED",
              "math_history_api": "math.history.result.v1.1",
              "scientific_api": "NOT_EXECUTED",
              "observed_prices": prices, "forecast_points": forecasts,
              "oos_metrics": review["oos_metrics"],
              "training_authorized": False, "execution_authority": False,
              "trading_authorized": False}
    packet["handoff_sha256"] = digest(packet)
    return packet
