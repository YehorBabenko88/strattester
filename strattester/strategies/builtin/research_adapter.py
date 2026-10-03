from __future__ import annotations
from strattester.strategies.base import DataRequirement,StrategyDefinition
from .research_common import HypothesisSpec
from strattester.research.execution import ExecutionPolicy,Signal,simulate_trade
from strattester.research.statistics import evaluate_trades
from dataclasses import asdict

def _bars(context,timeframe='1m'):
    return [
        {'t':c.open_time,'open':c.open,'high':c.high,'low':c.low,'close':c.close,
         'volume':c.volume,'turnover':c.turnover or 0.0}
        for c in context.candles(timeframe)
    ]

class ResearchHypothesisStrategy:
    spec:HypothesisSpec
    def _backtest(self,bars,events):
        trades=[]; busy_until=-1
        for event in events:
            kind=getattr(event,'kind','')
            if not any(x in kind for x in ('bos','choch','liquidity_sweep')): continue
            side='long' if kind.startswith('bullish') else 'short'
            future=[b for b in bars if b['t']>=event.known_at]
            if len(future)<2 or event.known_at<=busy_until: continue
            px=float(future[0]['open']); risk=max(px*.005,1e-12)
            signal=Signal(event.known_at,side,'market',None,px-risk if side=='long' else px+risk,px+2*risk if side=='long' else px-2*risk)
            try:
                trade=simulate_trade(signal,future,ExecutionPolicy(bar_ms=60_000))
                trades.append(trade); busy_until=trade.exit_time
            except ValueError: pass
        return trades
    def _signal_trade(self,bars,decision_time,side,risk_pct=.005,rr=2.0,metadata=None):
        future=[b for b in bars if b['t']>=decision_time]
        if len(future)<2:return None
        px=float(future[0]['open']); risk=max(px*risk_pct,1e-12)
        s=Signal(decision_time,side,'market',None,px-risk if side=='long' else px+risk,px+rr*risk if side=='long' else px-rr*risk)
        try:return simulate_trade(s,future,ExecutionPolicy(bar_ms=60_000),metadata=metadata)
        except ValueError:return None
    def _append_non_overlapping(self,trades,trade):
        if trade is not None and (not trades or trade.entry_time>trades[-1].exit_time):
            trades.append(trade)
    def _result(self,spec,trades,**extra):
        return {'hypothesis':spec.name,'family':spec.family,'trades':[asdict(x) for x in trades],
                'metrics':asdict(evaluate_trades(trades)),**extra}
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
            trades=self._backtest(bars,features)
            return {'hypothesis':spec.name,'family':spec.family,'features':len(features),'trades':[asdict(x) for x in trades],'metrics':asdict(evaluate_trades(trades)),'checkpoint':checkpoint}
        if spec.family=='poc':
            from strattester.research.volume_profile import proxy_profile
            if not bars:return {'hypothesis':spec.name,'family':spec.family,'snapshots':0,'checkpoint':checkpoint}
            snaps=[proxy_profile(bars[:i+1],known_at=b['t']+60_000) for i,b in enumerate(bars)]
            trades=[]
            mode=spec.params.get('mode')
            for i,snap in enumerate(snaps[:-1]):
                nxt=bars[i+1] if i+1<len(bars) else None
                if not nxt:continue
                close=float(bars[i]['close']); side=None
                if mode=='mean_reversion':
                    if close<snap.val: side='long'
                    elif close>snap.vah: side='short'
                elif mode in ('breakout_retest','migration'):
                    if close>snap.vah: side='long'
                    elif close<snap.val: side='short'
                elif mode=='rejection':
                    if close<=snap.val: side='long'
                    elif close>=snap.vah: side='short'
                if side:
                    t=self._signal_trade(bars,snap.known_at,side,metadata={'poc_mode':snap.mode.value})
                    self._append_non_overlapping(trades,t)
            return self._result(spec,trades,snapshots=len(snaps),last_poc=snaps[-1].poc,mode=snaps[-1].mode.value,checkpoint=checkpoint)
        if spec.family=='volatility':
            from strattester.research.volatility import VolatilityObservatory
            snaps=VolatilityObservatory().snapshots(bars,bar_ms=60_000)
            trades=[]
            wanted=spec.params.get('setup')
            for snap in snaps:
                idx=next((i for i,b in enumerate(bars) if b['t']==snap.event_time),None)
                if idx is None or idx<1:continue
                prev=float(bars[idx-1]['close']); cur=float(bars[idx]['close'])
                side='long' if cur>prev else 'short'
                fire=(wanted=='compression_expansion' and snap.regime.value in ('HIGH','EXTREME')) or (wanted=='continuation' and snap.regime.value in ('HIGH','EXTREME')) or (wanted=='exhaustion' and snap.regime.value=='EXTREME')
                if fire:
                    t=self._signal_trade(bars,snap.known_at,side if wanted!='exhaustion' else ('short' if side=='long' else 'long'),metadata={'volatility':snap.regime.value})
                    self._append_non_overlapping(trades,t)
            return self._result(spec,trades,snapshots=len(snaps),last_regime=snaps[-1].regime.value if snaps else None,checkpoint=checkpoint)
        if spec.family=='orderflow':
            from strattester.research.orderflow import cumulative_delta
            rows=list(context.public_trade_aggregates('1m'))
            points=cumulative_delta([{'t':r['open_time'],'buy_volume':r['buy_volume'],'sell_volume':r['sell_volume']} for r in rows])
            trades=[]
            for p in points:
                delta=float(p['delta'])
                if delta==0:continue
                side='long' if delta>0 else 'short'
                t=self._signal_trade(bars,int(p['known_at'])+60_000,side,metadata={'cvd':p['cvd'],'delta':delta})
                if t:trades.append(t)
            return self._result(spec,trades,aggregates=len(rows),checkpoint=checkpoint)
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
