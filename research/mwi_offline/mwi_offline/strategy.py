"""Finite declarative synthetic research candidates; no executable strategies."""
import copy
import math
import re
from .evaluation import digest

KEYS={'schema','strategy_id','version','parent_id','dataset_id','model_hash','family','entry','required_features',
      'threshold','position_usd','capital_usd','max_risk_fraction','max_drawdown','stop_atr','target_atr',
      'horizon','instruments','regime','mode','promotion_allowed','execution'}


def _seal(c):
    c['strategy_id']=digest({k:v for k,v in c.items() if k!='strategy_id'})
    return c


def validate(c):
    if type(c) is not dict or set(c)!=KEYS or c['schema']!='mwi.synthetic.strategy.v1':raise ValueError('STRATEGY_SCHEMA')
    for k in ('strategy_id','dataset_id','model_hash'):
        if type(c[k]) is not str or re.fullmatch('[0-9a-f]{64}',c[k]) is None:raise ValueError('STRATEGY_IDENTITY')
    if c['parent_id'] is not None and (type(c['parent_id']) is not str or re.fullmatch('[0-9a-f]{64}',c['parent_id']) is None):raise ValueError('PARENT_ID')
    if type(c['version']) is not int or not 1<=c['version']<=2:raise ValueError('VERSION_BUDGET')
    if c['mode']!='SIMULATION_ONLY' or c['promotion_allowed'] is not False:raise ValueError('MODE_REFUSED')
    if c['family'] not in ('wait','bounce_rule','baseline_probability','graph_probability'):raise ValueError('FAMILY_REFUSED')
    if c['entry']!={'kind':'market_next_full_bar'} or c['required_features'] not in (['baseline'],['baseline','graph']):raise ValueError('DECLARATIVE_ONLY')
    if c['instruments']!=['TOYUSDT'] or c['regime']!='SYNTHETIC_ALL':raise ValueError('SCOPE_REFUSED')
    for k,lo,hi in (('threshold',.55,.95),('position_usd',1.,100.),('capital_usd',1000.,1000.),
                     ('max_risk_fraction',.005,.005),('max_drawdown',.10,.10),('stop_atr',.8,.8),('target_atr',.8,.8)):
        if type(c[k]) not in (int,float) or not math.isfinite(c[k]) or not lo<=c[k]<=hi:raise ValueError('FIXED_RISK_BOUNDARY')
    if type(c['horizon']) is not int or c['horizon']!=12:raise ValueError('HORIZON_REFUSED')
    if c['execution']!={'fee_rate':.00055,'slippage_bps':2.,'latency_ms':60000,'funding':'SYNTHETIC_ZERO_ASSUMPTION','fill_model':'EXISTING_OHLC_SL_FIRST'}:raise ValueError('EXECUTION_ASSUMPTIONS')
    if digest({k:v for k,v in c.items() if k!='strategy_id'})!=c['strategy_id']:raise ValueError('STRATEGY_HASH')
    return c


def candidates(dataset_id,model_hash):
    result=[]
    for family,threshold in (('wait',.6),('bounce_rule',.6),('baseline_probability',.6),('baseline_probability',.75),('graph_probability',.6),('graph_probability',.75)):
        c=dict(schema='mwi.synthetic.strategy.v1',version=1,parent_id=None,dataset_id=dataset_id,model_hash=model_hash,
               family=family,entry={'kind':'market_next_full_bar'},required_features=['baseline','graph'] if family=='graph_probability' else ['baseline'],
               threshold=threshold,position_usd=100.,capital_usd=1000.,max_risk_fraction=.005,max_drawdown=.10,
               stop_atr=.8,target_atr=.8,horizon=12,instruments=['TOYUSDT'],regime='SYNTHETIC_ALL',mode='SIMULATION_ONLY',promotion_allowed=False,
               execution={'fee_rate':.00055,'slippage_bps':2.,'latency_ms':60000,'funding':'SYNTHETIC_ZERO_ASSUMPTION','fill_model':'EXISTING_OHLC_SL_FIRST'})
        result.append(validate(_seal(c)))
    return result


def propose(strategy,example,p):
    validate(strategy)
    if type(p) is not list or len(p)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=1 for x in p) or abs(sum(p)-1)>1e-8:raise ValueError('PROBABILITIES')
    v=example['baseline']
    if len(v)!=8 or v[0] not in (-1,1) or any(type(x) not in (int,float) or not math.isfinite(x) for x in v):raise ValueError('FEATURES')
    if strategy['family']=='wait':return {'action':'WAIT','reason':'BASELINE_WAIT'}
    outcome=1 if strategy['family']=='bounce_rule' else max(range(3),key=lambda i:p[i])
    if outcome==2 or (strategy['family']!='bounce_rule' and p[outcome]<strategy['threshold']):return {'action':'WAIT','reason':'CONFIDENCE_OR_TIMEOUT'}
    direction=v[0]*(1 if outcome==0 else -1)
    return {'action':'PROPOSE','side':'long' if direction==1 else 'short','reason':'DECLARATIVE_RULE','strategy_id':strategy['strategy_id']}


def next_version(parent,threshold):
    validate(parent)
    c=copy.deepcopy(parent);c.update(parent_id=parent['strategy_id'],version=parent['version']+1,threshold=threshold)
    return validate(_seal(c))
