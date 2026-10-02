def _latest_known(items,entry_time):
    eligible=[x for x in items if x.known_at<=entry_time]
    return max(eligible,key=lambda x:(x.known_at,getattr(x,'event_time',x.known_at))) if eligible else None

def attach_entry_context(*,entry_time:int,metadata:dict,volatility=(),profiles=()):
    out=dict(metadata)
    v=_latest_known(volatility,entry_time)
    if v is not None:
        out.update({
            'volatility_regime':v.regime.value,
            'volatility_percentile':v.percentile,
            'atr_pct':v.atr_pct,
            'realized_vol':v.realized_vol,
            'parkinson_vol':v.parkinson_vol,
            'volume_expansion':v.volume_expansion,
            'turnover_expansion':v.turnover_expansion,
            'volatility_version':v.version,
        })
    p=_latest_known(profiles,entry_time)
    if p is not None:
        out.update({'poc':p.poc,'vah':p.vah,'val':p.val,'poc_mode':p.mode.value,'value_area_width':p.value_area_width})
    return out
