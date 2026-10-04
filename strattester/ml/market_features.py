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

def attach_external_series(rows,*,open_interest=(),long_short_ratio=(),funding=(),open_interest_bar_ms=300_000,long_short_bar_ms=300_000):
    oi=sorted((dict(x) for x in open_interest),key=lambda x:int(x.get('t',x.get('open_time',0))))
    ls=sorted((dict(x) for x in long_short_ratio),key=lambda x:int(x.get('t',x.get('open_time',0))))
    fd=sorted((dict(x) for x in funding),key=lambda x:int(x.get('t',x.get('funding_time',0))))
    out=[]
    for row in rows:
        known=int(row.known_at); values=dict(row.values)
        prior_oi=[x for x in oi if int(x.get('known_at',int(x.get('t',x.get('open_time',0)))+open_interest_bar_ms))<=known]
        if prior_oi:
            cur=float(prior_oi[-1].get('value',0.0)); prev=float(prior_oi[-2].get('value',cur)) if len(prior_oi)>1 else cur
            values['open_interest']=cur
            values['open_interest_change']=cur/prev-1.0 if prev else 0.0
        prior_ls=[x for x in ls if int(x.get('known_at',int(x.get('t',x.get('open_time',0)))+long_short_bar_ms))<=known]
        if prior_ls:
            values['long_short_ratio']=float(prior_ls[-1].get('long_short_ratio',0.0) or 0.0)
        prior_fd=[x for x in fd if int(x.get('known_at',x.get('t',x.get('funding_time',0))))<=known]
        if prior_fd:
            values['funding_rate']=float(prior_fd[-1].get('rate',0.0))
        out.append(replace(row,values=values))
    return tuple(out)


def attach_live_microstructure(rows,snapshots=(),*,max_age_ms=15000):
    """Attach only snapshots known by row. Missing/stale data are explicit, never silently zero-valued."""
    snaps=sorted((dict(x) for x in snapshots),key=lambda x:int(x.get('known_at',x.get('t',0))))
    out=[]; j=-1
    def ratio(a,b): return a/b if b else 0.0
    def imb(a,b): return ratio(a-b,a+b)
    for row in rows:
        known=int(row.known_at)
        while j+1<len(snaps) and int(snaps[j+1].get('known_at',snaps[j+1].get('t',0)))<=known: j+=1
        values=dict(row.values)
        if j<0:
            values.update({'micro_available':0.0,'micro_stale':0.0,'micro_age_ms':-1.0})
        else:
            s=snaps[j]; sk=int(s.get('known_at',s.get('t',0))); age=known-sk
            if age>int(max_age_ms):
                values.update({'micro_available':0.0,'micro_stale':1.0,'micro_age_ms':float(age)})
            else:
                bid=float(s.get('bid',0)); ask=float(s.get('ask',0)); mid=(bid+ask)/2 if bid and ask else 0.0
                b1=float(s.get('bid_depth_1',0)); a1=float(s.get('ask_depth_1',0))
                b5=float(s.get('bid_depth_5',0)); a5=float(s.get('ask_depth_5',0))
                b25=float(s.get('bid_depth_25',0)); a25=float(s.get('ask_depth_25',0))
                buy=float(s.get('buy_volume',0)); sell=float(s.get('sell_volume',0)); total=buy+sell
                lb=float(s.get('large_buy_volume',0)); ls=float(s.get('large_sell_volume',0)); large=lb+ls
                addb=float(s.get('added_bid',0)); adda=float(s.get('added_ask',0))
                remb=float(s.get('removed_bid',0)); rema=float(s.get('removed_ask',0))
                values.update({
                    'micro_available':1.0,'micro_stale':0.0,'micro_age_ms':float(age),
                    'micro_book_reset':float(bool(s.get('book_reset',False))),
                    'micro_book_gap':float(bool(s.get('book_gap',False))),
                    'micro_trade_gap':float(bool(s.get('trade_gap',False))),
                    'micro_spread_pct':ratio(ask-bid,mid),
                    'micro_depth_imbalance_1':imb(b1,a1),'micro_depth_imbalance_5':imb(b5,a5),
                    'micro_depth_imbalance_25':imb(b25,a25),
                    'micro_trade_delta':buy-sell,'micro_trade_imbalance':ratio(buy-sell,total),
                    'micro_trade_count':float(s.get('trade_count',0)),
                    'micro_large_trade_share':ratio(large,total),
                    'micro_large_trade_imbalance':ratio(lb-ls,large),
                    'micro_added_liquidity_imbalance':imb(addb,adda),
                    'micro_removed_liquidity_imbalance':imb(remb,rema),
                    'micro_book_pressure':imb(b1+.5*b5,a1+.5*a5),
                    'micro_buy_absorption':ratio(buy,rema+adda),
                    'micro_sell_absorption':ratio(sell,remb+addb),
                })
                if mid and b1+a1:
                    mp=(ask*b1+bid*a1)/(b1+a1)
                    values['micro_microprice_vs_mid']=ratio(mp-mid,mid)
                else: values['micro_microprice_vs_mid']=0.0
        out.append(replace(row,values=values))
    return tuple(out)
