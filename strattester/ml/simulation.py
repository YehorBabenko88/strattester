from __future__ import annotations
from dataclasses import dataclass
from strattester.research.execution import ExecutionPolicy,Signal,simulate_trade

@dataclass(frozen=True)
class MLSimulationPolicy:
    probability_threshold:float=.60
    min_confidence:float=.20
    stop_pct:float=.005
    reward_risk:float=2.0
    bar_ms:int=60_000
    fee_rate:float=.00055
    slippage_bps:float=0.0
    position_usd:float=100.0

def simulate_frozen_pipeline(pipeline,context_bars,simulation_bars,*,policy=MLSimulationPolicy(),
                             public_trade_aggregates=(),simulation_start_ms=None,purge=None,**feature_kwargs):
    if pipeline.snapshot is None:
        raise RuntimeError('simulation requires a frozen walk-forward snapshot')
    sim=sorted((dict(x) for x in simulation_bars),key=lambda x:int(x['t']))
    if not sim:return ()
    start=int(simulation_start_ms if simulation_start_ms is not None else sim[0]['t'])
    pipeline.assert_simulation_safe(simulation_start_ms=start,bar_ms=policy.bar_ms,purge=purge)
    base=[dict(x) for x in context_bars if int(x['t'])<start]
    trades=[]; busy_until=-1
    execution=ExecutionPolicy(
        bar_ms=policy.bar_ms,fee_rate=policy.fee_rate,slippage_bps=policy.slippage_bps,
        position_usd=policy.position_usd)
    for i,current in enumerate(sim):
        history=base+sim[:i+1]
        ml=pipeline.signal(history,public_trade_aggregates,**feature_kwargs)
        if ml.confidence<policy.min_confidence:continue
        if ml.probability_up>=policy.probability_threshold:
            side='long'
        elif ml.probability_up<=1.0-policy.probability_threshold:
            side='short'
        else:
            continue
        if ml.known_at<=busy_until:continue
        future=sim[i+1:]
        if not future:continue
        px=float(future[0]['open'])
        risk=max(px*policy.stop_pct,1e-12)
        sig=Signal(
            ml.known_at,side,'market',None,
            px-risk if side=='long' else px+risk,
            px+policy.reward_risk*risk if side=='long' else px-policy.reward_risk*risk)
        try:
            trade=simulate_trade(sig,future,execution,metadata={
                'ml_probability_up':ml.probability_up,'ml_confidence':ml.confidence,
                'ml_expected_return':ml.expected_return,'ml_regime':ml.regime,
                'model_trained_until':pipeline.snapshot.trained_until})
        except ValueError:
            continue
        trades.append(trade); busy_until=trade.exit_time
    return tuple(trades)
