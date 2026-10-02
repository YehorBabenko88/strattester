from dataclasses import dataclass
from enum import Enum

class POCMode(str,Enum):
    POC_PROXY='POC_PROXY'; TRADE_POC='TRADE_POC'

@dataclass(frozen=True)
class VolumeProfileSnapshot:
    poc:float; vah:float; val:float; known_at:int; mode:POCMode; value_area_width:float

def _profile(points,known_at,mode):
    volume={}
    for t,p,v in points:
        if t<=known_at: volume[p]=volume.get(p,0.0)+v
    if not volume: raise ValueError('no observations available at known_at')
    poc=max(volume,key=lambda p:(volume[p],-p))
    total=sum(volume.values()); target=total*.70
    ranked=sorted(volume,key=lambda p:volume[p],reverse=True); acc=0; selected=[]
    for p in ranked:
        selected.append(p); acc+=volume[p]
        if acc>=target: break
    val=min(selected); vah=max(selected)
    return VolumeProfileSnapshot(poc,vah,val,known_at,mode,vah-val)

def trade_profile(trades,*,known_at:int):
    return _profile(((x['t'],x['price'],x['volume']) for x in trades),known_at,POCMode.TRADE_POC)

def proxy_profile(bars,*,known_at:int):
    return _profile(((x['t'],(x['high']+x['low']+x['close'])/3,x['volume']) for x in bars),known_at,POCMode.POC_PROXY)
