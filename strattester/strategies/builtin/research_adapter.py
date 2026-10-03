from __future__ import annotations
from strattester.strategies.base import DataRequirement,StrategyDefinition
from .research_common import HypothesisSpec

def _bars(context,timeframe='1m'):
    return [
        {'t':c.open_time,'open':c.open,'high':c.high,'low':c.low,'close':c.close,
         'volume':c.volume,'turnover':c.turnover or 0.0}
        for c in context.candles(timeframe)
    ]

class ResearchHypothesisStrategy:
    spec:HypothesisSpec
    def run_context(self,context,checkpoint=None):
        spec=self.spec
        bars=_bars(context,'1m')
        if spec.family=='levels':
            from strattester.research.levels import completed_period_levels
            features=completed_period_levels(bars,period_ms=60*60*1000,next_bar_ms=60_000) if bars else ()
            return {'hypothesis':spec.name,'family':spec.family,'features':len(features),'checkpoint':checkpoint}
        if spec.family=='smc':
            from strattester.research.smc import market_structure
            features=market_structure(bars,bar_ms=60_000) if bars else ()
            wanted=spec.params.get('setup')
            if wanted=='order_block': features=tuple(x for x in features if 'order_block' in x.kind)
            elif wanted=='liquidity_sweep': features=tuple(x for x in features if 'liquidity_sweep' in x.kind)
            elif wanted=='momentum': features=tuple(x for x in features if x.kind.endswith(('bos','choch')))
            confirm=spec.params.get('confirm')
            if confirm: features=tuple(x for x in features if confirm in x.kind or wanted=='order_block')
            return {'hypothesis':spec.name,'family':spec.family,'features':len(features),'checkpoint':checkpoint}
        if spec.family=='poc':
            from strattester.research.volume_profile import proxy_profile
            if not bars:return {'hypothesis':spec.name,'family':spec.family,'snapshots':0,'checkpoint':checkpoint}
            snaps=[proxy_profile(bars[:i+1],known_at=b['t']+60_000) for i,b in enumerate(bars)]
            return {'hypothesis':spec.name,'family':spec.family,'snapshots':len(snaps),'last_poc':snaps[-1].poc,'mode':snaps[-1].mode.value,'checkpoint':checkpoint}
        if spec.family=='volatility':
            from strattester.research.volatility import VolatilityObservatory
            snaps=VolatilityObservatory().snapshots(bars,bar_ms=60_000)
            return {'hypothesis':spec.name,'family':spec.family,'snapshots':len(snaps),'last_regime':snaps[-1].regime.value if snaps else None,'checkpoint':checkpoint}
        if spec.family=='orderflow':
            rows=list(context.public_trade_aggregates('1m'))
            return {'hypothesis':spec.name,'family':spec.family,'aggregates':len(rows),'checkpoint':checkpoint}
        raise ValueError(f'unsupported hypothesis family: {spec.family}')

def _implementation(spec):
    return type(spec.name,(ResearchHypothesisStrategy,),{'spec':spec,'__module__':__name__})

def hypothesis_definition(spec:HypothesisSpec)->StrategyDefinition:
    requirements=[DataRequirement('candles',('1m',))]
    if spec.family=='orderflow':
        requirements.append(DataRequirement('public_trade_aggregates',('1m',)))
    if spec.params.get('confirm')=='open_interest':
        requirements.append(DataRequirement('open_interest',('5m',)))
    return StrategyDefinition(
        id=spec.name.lower(),version='1.0',requirements=tuple(requirements),
        implementation=_implementation(spec),feature_versions=(f'{spec.family}-v1',))
