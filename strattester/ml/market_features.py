from __future__ import annotations
from dataclasses import replace
from .features import FeatureRow

def _latest(events,known_at):
    return [x for x in events if int(x.known_at)<=int(known_at)]

def enrich_research_features(rows,bars,*,bar_ms=60_000,profile_window=120,level_period_ms=3_600_000):
    from strattester.research.smc import market_structure
    from strattester.research.levels import completed_period_levels
    from strattester.research.volume_profile import proxy_profile
    from strattester.research.volatility import VolatilityObservatory

    bars=sorted((dict(x) for x in bars),key=lambda x:int(x['t']))
    by_t={int(b['t']):i for i,b in enumerate(bars)}
    smc=market_structure(bars,bar_ms=bar_ms) if bars else ()
    levels=completed_period_levels(bars,period_ms=level_period_ms,next_bar_ms=bar_ms) if bars else ()
    vol=VolatilityObservatory().snapshots(bars,bar_ms=bar_ms) if bars else ()
    out=[]
    for row in rows:
        idx=by_t.get(int(row.timestamp))
        if idx is None:continue
        known=int(row.known_at); close=float(bars[idx]['close']); values=dict(row.values)

        visible_smc=_latest(smc,known)
        recent=visible_smc[-1] if visible_smc else None
        values.update({
            'smc_bullish_bos':float(bool(recent and recent.kind=='bullish_bos')),
            'smc_bearish_bos':float(bool(recent and recent.kind=='bearish_bos')),
            'smc_bullish_choch':float(bool(recent and recent.kind=='bullish_choch')),
            'smc_bearish_choch':float(bool(recent and recent.kind=='bearish_choch')),
            'smc_bullish_sweep':float(bool(recent and recent.kind=='bullish_liquidity_sweep')),
            'smc_bearish_sweep':float(bool(recent and recent.kind=='bearish_liquidity_sweep')),
        })

        visible_levels=_latest(levels,known)
        highs=[x for x in visible_levels if x.kind=='period_high']
        lows=[x for x in visible_levels if x.kind=='period_low']
        high=float(highs[-1].value) if highs else close
        low=float(lows[-1].value) if lows else close
        values['distance_period_high']=(high-close)/close if close else 0.0
        values['distance_period_low']=(close-low)/close if close else 0.0

        history=bars[max(0,idx-profile_window+1):idx+1]
        snap=proxy_profile(history,known_at=known)
        values['distance_poc']=(close-snap.poc)/close if close else 0.0
        values['distance_vah']=(close-snap.vah)/close if close else 0.0
        values['distance_val']=(close-snap.val)/close if close else 0.0
        values['value_area_width_pct']=snap.value_area_width/close if close else 0.0

        visible_vol=_latest(vol,known)
        if visible_vol:
            v=visible_vol[-1]
            values.update({
                'vol_atr_pct':v.atr_pct,'vol_realized':v.realized_vol,
                'vol_parkinson':v.parkinson_vol,'vol_percentile':v.percentile,
                'vol_volume_expansion':v.volume_expansion,
                'vol_turnover_expansion':v.turnover_expansion,
            })
        out.append(replace(row,values=values))
    return tuple(out)

def attach_external_series(rows,*,open_interest=(),long_short_ratio=(),funding=()):
    oi=sorted((dict(x) for x in open_interest),key=lambda x:int(x.get('t',x.get('open_time',0))))
    ls=sorted((dict(x) for x in long_short_ratio),key=lambda x:int(x.get('t',x.get('open_time',0))))
    fd=sorted((dict(x) for x in funding),key=lambda x:int(x.get('t',x.get('funding_time',0))))
    out=[]
    for row in rows:
        known=int(row.known_at); values=dict(row.values)
        prior_oi=[x for x in oi if int(x.get('t',x.get('open_time',0)))<=known]
        if prior_oi:
            cur=float(prior_oi[-1].get('value',0.0)); prev=float(prior_oi[-2].get('value',cur)) if len(prior_oi)>1 else cur
            values['open_interest']=cur
            values['open_interest_change']=cur/prev-1.0 if prev else 0.0
        prior_ls=[x for x in ls if int(x.get('t',x.get('open_time',0)))<=known]
        if prior_ls:
            values['long_short_ratio']=float(prior_ls[-1].get('long_short_ratio',0.0) or 0.0)
        prior_fd=[x for x in fd if int(x.get('t',x.get('funding_time',0)))<=known]
        if prior_fd:
            values['funding_rate']=float(prior_fd[-1].get('rate',0.0))
        out.append(replace(row,values=values))
    return tuple(out)
