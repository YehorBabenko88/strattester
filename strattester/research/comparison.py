from __future__ import annotations

def strategy_summary(rows):
    out=[]
    for row in rows:
        metrics=(row.get('metrics') or {}).get('output',{}).get('metrics',{})
        out.append({
            'symbol':row.get('symbol'),
            'strategy_id':row.get('strategy_id'),
            'strategy_version':row.get('strategy_version'),
            'trades':metrics.get('trades',0),
            'net_pnl':metrics.get('net_pnl',0.0),
            'profit_factor':metrics.get('profit_factor',0.0),
            'max_drawdown':metrics.get('max_drawdown',0.0),
            'win_rate':metrics.get('win_rate',0.0),
            'expectancy':metrics.get('expectancy',0.0),
        })
    return out
