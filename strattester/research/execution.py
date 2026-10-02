from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ExecutionPolicy:
    bar_ms:int
    fee_rate:float=.00055
    slippage_bps:float=0.0
    ambiguous_policy:str='SL_FIRST'
    position_usd:float=100.0

@dataclass(frozen=True)
class Signal:
    decision_time:int
    side:str
    entry_kind:str
    entry_price:float|None
    stop_loss:float
    take_profit:float

@dataclass(frozen=True)
class ResearchTrade:
    side:str
    entry_time:int
    entry_price:float
    exit_time:int
    exit_price:float
    exit_reason:str
    gross_pnl:float
    fees:float
    net_pnl:float
    metadata:dict=field(default_factory=dict)

def _adverse(price:float,side:str,bps:float,entry:bool)->float:
    k=bps/10000.0
    if side=='long':
        return price*(1+k if entry else 1-k)
    return price*(1-k if entry else 1+k)

def simulate_trade(signal:Signal,bars,policy:ExecutionPolicy,metadata=None)->ResearchTrade:
    if signal.side not in ('long','short'): raise ValueError('side')
    if signal.entry_kind not in ('market','limit'): raise ValueError('entry_kind')
    rows=list(bars)
    entry_idx=None; raw_entry=None
    for i,b in enumerate(rows):
        earliest = signal.decision_time if signal.entry_kind=='market' else signal.decision_time + policy.bar_ms
        if b['t'] < earliest: continue
        if signal.entry_kind=='market':
            entry_idx=i; raw_entry=float(b['open']); break
        p=float(signal.entry_price)
        o=float(b['open']); h=float(b['high']); l=float(b['low'])
        if signal.side=='long':
            if o<=p:
                entry_idx=i; raw_entry=o; break
            if l<=p<=h:
                entry_idx=i; raw_entry=p; break
        else:
            if o>=p:
                entry_idx=i; raw_entry=o; break
            if l<=p<=h:
                entry_idx=i; raw_entry=p; break
    if entry_idx is None: raise ValueError('entry not filled')
    entry=_adverse(raw_entry,signal.side,policy.slippage_bps,True)
    exit_time=None; raw_exit=None; reason=None
    for b in rows[entry_idx+1:]:
        o=float(b['open']); h=float(b['high']); l=float(b['low'])
        if signal.side=='long':
            if o <= signal.stop_loss:
                raw_exit=o; reason='SL_GAP'
            elif o >= signal.take_profit:
                raw_exit=signal.take_profit; reason='TP_GAP'
            else:
                hit_sl=l <= signal.stop_loss
                hit_tp=h >= signal.take_profit
                if hit_sl and hit_tp:
                    raw_exit=signal.stop_loss if policy.ambiguous_policy=='SL_FIRST' else signal.take_profit
                    reason='SL' if policy.ambiguous_policy=='SL_FIRST' else 'TP'
                elif hit_sl:
                    raw_exit=signal.stop_loss; reason='SL'
                elif hit_tp:
                    raw_exit=signal.take_profit; reason='TP'
        else:
            if o >= signal.stop_loss:
                raw_exit=o; reason='SL_GAP'
            elif o <= signal.take_profit:
                raw_exit=signal.take_profit; reason='TP_GAP'
            else:
                hit_sl=h >= signal.stop_loss
                hit_tp=l <= signal.take_profit
                if hit_sl and hit_tp:
                    raw_exit=signal.stop_loss if policy.ambiguous_policy=='SL_FIRST' else signal.take_profit
                    reason='SL' if policy.ambiguous_policy=='SL_FIRST' else 'TP'
                elif hit_sl:
                    raw_exit=signal.stop_loss; reason='SL'
                elif hit_tp:
                    raw_exit=signal.take_profit; reason='TP'
        if reason:
            exit_time=b['t']; break
    if reason is None:
        b=rows[-1]; raw_exit=float(b['close']); exit_time=b['t']; reason='EOD'
    exit_price=_adverse(float(raw_exit),signal.side,policy.slippage_bps,False)
    qty=policy.position_usd/entry if entry else 0.0
    gross=(exit_price-entry)*qty if signal.side=='long' else (entry-exit_price)*qty
    fees=(entry+exit_price)*qty*policy.fee_rate
    return ResearchTrade(signal.side,rows[entry_idx]['t'],entry,exit_time,exit_price,reason,gross,fees,gross-fees,dict(metadata or {}))


@dataclass(frozen=True)
class ScaleSignal:
    decision_time:int
    side:str
    entries:tuple[tuple[float,float],...]
    stop_loss:float
    take_profits:tuple[tuple[float,float],...]

@dataclass(frozen=True)
class ExecutionFill:
    time:int
    price:float
    quantity:float
    fraction:float

@dataclass(frozen=True)
class ExecutionExit:
    time:int
    price:float
    quantity:float
    reason:str

@dataclass(frozen=True)
class ScaleTrade:
    side:str
    fills:tuple[ExecutionFill,...]
    exits:tuple[ExecutionExit,...]
    gross_pnl:float
    fees:float
    net_pnl:float

def simulate_scale_trade(signal:ScaleSignal,bars,policy:ExecutionPolicy)->ScaleTrade:
    if signal.side not in ('long','short'): raise ValueError('side')
    if not signal.entries or abs(sum(x[1] for x in signal.entries)-1.0)>1e-9: raise ValueError('entry fractions')
    if not signal.take_profits or abs(sum(x[1] for x in signal.take_profits)-1.0)>1e-9: raise ValueError('target fractions')
    rows=list(bars); fills=[]; entry_notional=0.0
    first_allowed=signal.decision_time+policy.bar_ms
    for price,fraction in signal.entries:
        for b in rows:
            if b['t']<first_allowed: continue
            o=float(b['open']); h=float(b['high']); l=float(b['low'])
            hit=(o<=price or l<=price<=h) if signal.side=='long' else (o>=price or l<=price<=h)
            if not hit: continue
            raw=o if ((signal.side=='long' and o<=price) or (signal.side=='short' and o>=price)) else float(price)
            px=_adverse(raw,signal.side,policy.slippage_bps,True)
            qty=(policy.position_usd*fraction)/px
            fills.append(ExecutionFill(b['t'],px,qty,fraction)); entry_notional+=px*qty
            break
    if not fills: raise ValueError('entry not filled')
    total_qty=sum(x.quantity for x in fills); remaining=total_qty; exits=[]
    first_fill=min(x.time for x in fills)
    targets=list(signal.take_profits)
    for idx,(target,fraction) in enumerate(targets,1):
        desired=total_qty*fraction
        for b in rows:
            if b['t']<=first_fill or remaining<=0: continue
            o=float(b['open']); h=float(b['high']); l=float(b['low'])
            stop_hit=(o<=signal.stop_loss or l<=signal.stop_loss) if signal.side=='long' else (o>=signal.stop_loss or h>=signal.stop_loss)
            target_hit=(o>=target or h>=target) if signal.side=='long' else (o<=target or l<=target)
            if stop_hit:
                raw=o if ((signal.side=='long' and o<=signal.stop_loss) or (signal.side=='short' and o>=signal.stop_loss)) else signal.stop_loss
                q=remaining; px=_adverse(raw,signal.side,policy.slippage_bps,False)
                exits.append(ExecutionExit(b['t'],px,q,'SL')); remaining=0; break
            if target_hit:
                q=min(desired,remaining); px=_adverse(float(target),signal.side,policy.slippage_bps,False)
                exits.append(ExecutionExit(b['t'],px,q,f'TP{idx}')); remaining-=q; break
        if remaining<=0: break
    if remaining>1e-12:
        b=rows[-1]; px=_adverse(float(b['close']),signal.side,policy.slippage_bps,False)
        exits.append(ExecutionExit(b['t'],px,remaining,'EOD')); remaining=0
    avg_entry=sum(x.price*x.quantity for x in fills)/total_qty
    gross=sum((x.price-avg_entry)*x.quantity if signal.side=='long' else (avg_entry-x.price)*x.quantity for x in exits)
    fees=(sum(x.price*x.quantity for x in fills)+sum(x.price*x.quantity for x in exits))*policy.fee_rate
    return ScaleTrade(signal.side,tuple(fills),tuple(exits),gross,fees,gross-fees)
