def cumulative_delta(rows):
    cvd=0.0; out=[]
    for r in rows:
        delta=float(r.get('buy_volume',0))-float(r.get('sell_volume',0))
        cvd+=delta
        out.append({**r,'delta':delta,'cvd':cvd,'known_at':r['t']})
    return tuple(out)

def aggression_decay(rows,*,side:str,window:int=3):
    xs=list(rows)[-window:]
    if len(xs)<window:return None
    key='sell_volume' if side=='sell' else 'buy_volume'
    vals=[float(x.get(key,0)) for x in xs]
    return {'side':side,'known_at':xs[-1]['t'],'values':tuple(vals),
            'decaying':all(a>b for a,b in zip(vals,vals[1:]))}

def cvd_divergence(points,*,direction:str,lookback:int=3):
    xs=list(points)[-lookback:]
    if len(xs)<lookback:return False
    a=xs[-2]; b=xs[-1]
    if direction=='bullish':
        return float(b['price'])>=float(a['price']) and float(b['cvd'])>float(a['cvd'])
    if direction=='bearish':
        return float(b['price'])<=float(a['price']) and float(b['cvd'])<float(a['cvd'])
    raise ValueError('direction')
