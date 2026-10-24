# Explicit offline inference bridge (research only)

Entry point: strattester.research.financial_offline_bridge.run_verified_offline.

This function joins pinned snapshot bytes, a trusted-producer allowlist,
coherence ID, checkpoint digest, instrument/timeframe/horizon and typed
Prediction. It does not call ResearchRunner, SyncEngine, exchange clients,
SQLiteMarketStore.open, or order execution.

This is an opt-in library entry point, not a production strategy registration
or a secure process sandbox. It does NOT prevent arbitrary imported code from
opening sockets, and it does NOT authenticate the Grid producer independently.
The allowlist/coherence string and caller-provided SHA values are insufficient
to establish historical provenance. A trusted, signed producer receipt and
immutable export are still mandatory for real market data.

The bridge is deliberately not installed in the default strategy registry.
To use on a disposable research host, require separately verified input
artifacts, a network-denied process sandbox, OS filesystem confinement and
an explicit G1 authorization. Until then, use synthetic fixtures only.

Open gates: native Grid producer export, physical process/network isolation,
cross-store snapshot attestation, real OOS, GPU and full upstream equivalence.
Physical G1 NOT_AUTHORIZED; trading NO-GO.

## Superseding authenticated route (cycle2)

For signed producer exports use financial_signed_export.load_attested_export and financial_attested_inference.run_attested_offline, with explicit disabled research registry integration in strategies/builtin/financial_structural.py. This older run_verified_offline helper remains unauthenticated engineering-only and is not the accepted Grid trust boundary. See CYCLE2_SIGNED_OFFLINE_INTEGRATION.md; native producer truth, native process isolation and G1 remain BLOCKED.
