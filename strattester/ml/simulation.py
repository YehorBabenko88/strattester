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
                             public_trade_aggregates=(),simulation_start_ms=None,purge=None,
                             diagnostics=None,**feature_kwargs):
    if pipeline.snapshot is None:
        raise RuntimeError('simulation requires a frozen walk-forward snapshot')
    sim=sorted((dict(x) for x in simulation_bars),key=lambda x:int(x['t']))
    if not sim:return ()
    start=int(simulation_start_ms if simulation_start_ms is not None else sim[0]['t'])
    pipeline.assert_simulation_safe(simulation_start_ms=start,bar_ms=policy.bar_ms,purge=purge)
    base=[dict(x) for x in context_bars if int(x['t'])<start]
    # Build causal features once for the complete replay. Each FeatureRow carries
    # its own known_at boundary, so later market/external observations are not
    # exposed to earlier predictions. This avoids rebuilding the entire history
    # for every simulated bar.
    replay_bars=base+sim
    feature_rows=pipeline.feature_rows(
        replay_bars,public_trade_aggregates,
        open_interest=feature_kwargs.get('open_interest',()),
        long_short_ratio=feature_kwargs.get('long_short_ratio',()),
        funding=feature_kwargs.get('funding',()),
        strategy_observations=feature_kwargs.get('strategy_observations',()))
    features_by_t={int(row.timestamp):row for row in feature_rows}
    trades=[]; busy_until=-1
    prediction_rows=[]
    execution=ExecutionPolicy(
        bar_ms=policy.bar_ms,fee_rate=policy.fee_rate,slippage_bps=policy.slippage_bps,
        position_usd=policy.position_usd)
    for i,current in enumerate(sim):
        row=features_by_t.get(int(current['t']))
        if row is None:continue
        ml=pipeline.signal_from_feature_row(row)
        prediction_rows.append((i,ml))
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
    if diagnostics is not None:
        probs=[ml.probability_up for _,ml in prediction_rows]
        diagnostics.clear()
        diagnostics['predictions']=len(probs)
        diagnostics['probability_min']=min(probs) if probs else None
        diagnostics['probability_max']=max(probs) if probs else None
        diagnostics['probability_mean']=sum(probs)/len(probs) if probs else None
        ordered=sorted(probs)
        def q(v):
            if not ordered:return None
            pos=(len(ordered)-1)*v; lo=int(pos); hi=min(lo+1,len(ordered)-1); frac=pos-lo
            return ordered[lo]*(1-frac)+ordered[hi]*frac
        diagnostics['probability_quantiles']={k:q(v) for k,v in (
            ('p01',.01),('p05',.05),('p25',.25),('p50',.50),('p75',.75),('p95',.95),('p99',.99))}
        diagnostics['signal_counts']={
            str(x):sum(p>=x or p<=1.0-x for p in probs) for x in (.55,.60,.65)}
        diagnostics['policy_eligible']=sum(
            ml.confidence>=policy.min_confidence and (
                ml.probability_up>=policy.probability_threshold or
                ml.probability_up<=1.0-policy.probability_threshold)
            for _,ml in prediction_rows)
        regime={}
        for i,ml in prediction_rows:
            j=i+pipeline.horizon
            if j>=len(sim):continue
            now=float(sim[i]['close']); future=float(sim[j]['close']); y=int(future>now)
            bucket=regime.setdefault(str(ml.regime),[])
            bucket.append((ml.probability_up,y))
        diagnostics['regimes']={}
        for name,items in sorted(regime.items()):
            ys=[y for _,y in items]
            diagnostics['regimes'][name]={
                'samples':len(items),'positive_rate':sum(ys)/len(ys),
                'accuracy':sum((p>=.5)==bool(y) for p,y in items)/len(items),
                'brier':sum((p-y)**2 for p,y in items)/len(items),
                'probability_mean':sum(p for p,_ in items)/len(items)}
    return tuple(trades)
