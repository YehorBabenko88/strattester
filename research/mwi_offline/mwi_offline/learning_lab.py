"""Local proposal preview only; no Terminan imports, UI, routes or publication."""
from .unified_adapter import _plain,_sha,_hash
from .strategy import validate

DOMAINS=('dataset_readiness','model_versions','training_progress','strategy_candidates',
         'oos_results','simulated_pnl_and_risk','forecast_probabilities',
         'mwi_graph_visualizations','experiment_lineage')
TERMINAN_CONTEXT={'commit':'2a8e2647700dad4f661057235e13f76dc52f091f',
                  'tree':'718fed81b980e01b338ab21fdf093da4e3363121',
                  'role':'OWNER_REPORTED_SOURCE_CONTEXT_NOT_ADOPTION'}


def build_learning_lab_preview(strategies,artifact_sha256,*,source_head=None):
    """Summarize validated local candidates; unavailable domains stay empty.

    Artifact digest is caller-supplied identity, not file readback/publication.
    This is not unified.lab.market-paper.v2 or a producer scientific handoff.
    """
    _plain(strategies);_sha(artifact_sha256,64)
    if source_head is not None:_sha(source_head,40)
    if type(strategies) is not list or not 1<=len(strategies)<=6:raise ValueError('PREVIEW_CANDIDATE_BUDGET')
    for candidate in strategies:validate(candidate)
    ids=[s['strategy_id'] for s in strategies]
    if len(set(ids))!=len(ids) or len({s['dataset_id'] for s in strategies})!=1:
        raise ValueError('PREVIEW_COHORT_IDENTITY')
    domains={name:{'status':'PROPOSED_NOT_ADOPTED','data':None,
                   'missingness':'OWNER_SCHEMA_AND_SOURCE_EVIDENCE_UNAVAILABLE'} for name in DOMAINS}
    domains['strategy_candidates']['data']=[{'local_candidate_id':s['strategy_id'],'version':s['version'],
        'family':s['family'],'threshold':s['threshold'],'required_features':list(s['required_features']),
        'state':'LOCAL_RESEARCH_CANDIDATE_ONLY','promotion_allowed':False} for s in strategies]
    domains['strategy_candidates']['missingness']='OWNER_ADOPTION_UNAVAILABLE_LOCAL_PROPOSALS_ONLY'
    result=dict(schema='mwi.local.learning-lab-preview.v1',evidence_class='SYNTHETIC',
        publication_status='LOCAL_UNATTESTED',adoption_status='PROPOSED_NOT_ADOPTED',owner_field_ack='PENDING',
        source_context='UNKNOWN' if source_head is None else 'CALLER_SUPPLIED_NOT_AUTHENTICATED',
        source_head=source_head,terminan_source_context=dict(TERMINAN_CONTEXT),
        local_artifact_sha256=artifact_sha256,artifact_hash_verification='NOT_PERFORMED',
        local_dataset_id=strategies[0]['dataset_id'],domains=domains,
        owner_experiment_id=None,owner_job_id=None,endpoint=None,
        live=False,submitted=False,authenticated=False,source_admitted=False,
        execution_authority=False,training_authorized=False,trading_authorized=False,
        limitations=['INERT_PROPOSAL_NOT_OWNER_LAB_SCHEMA','NO_UI_OR_API_PUBLICATION',
                     'NO_MEASURED_QUEUE_RESOURCES_FORECASTS_OR_SIMULATION',
                     'PHYSICAL_AND_REAL_DATA_STATUS_UNKNOWN'])
    result['preview_sha256']=_hash(result)
    return result


# Strict reader profile for the existing stage-2 finite-cycle result, not a UI API.
import hashlib
import math
import os
import stat
import re
from .adapter import _safe,_json

_RESULT_KEYS=set('status config evaluated_candidates iterations candidates selected_strategy_id policy_holdout forecast_errors original_final_oos candidate_state promotion_allowed model_registry math_integration terminan_integration real_data rl'.split())
_CONFIG_KEYS=set('schema dataset_id source_head source_hash simulator_sha256 binding_scope max_candidates max_iterations development_only promotion_allowed policy_holdout_bars policy_holdout_seed policy_holdout_start_ms'.split())
_NATIVE_SHA='99c1a3a7907b0481c0f2a4f239fb6808f137834b39fffaf7885ef60f66246832'
_SCOPE='PINNED_EXISTING_PURE_SIMULATOR_SYNTHETIC_DEVELOPER_ONLY'


def _need(v):
    if not v:raise ValueError('ENGINE_RESULT_CONTRACT')


def _closed(v,keys):_need(type(v) is dict and set(v)==set(keys))


def _count(v,maximum=256):_need(type(v) is int and 0<=v<=maximum)


def _number(v,lo=-1e12,hi=1e12):
    _need(type(v) in (int,float) and math.isfinite(v) and lo<=v<=hi)


def _bounded_result(v,depth=0,budget=None):
    if budget is None:budget=[0]
    budget[0]+=1;_need(depth<=20 and budget[0]<=60000)
    t=type(v)
    if v is None or t is bool:return
    if t in (int,float):
        _number(v,-(2**53-1),2**53-1);return
    if t is str:_need(len(v)<=4096);return
    if t is list:
        _need(len(v)<=256)
        for x in v:_bounded_result(x,depth+1,budget)
        return
    if t is dict:
        _need(len(v)<=64)
        for k,x in v.items():
            _need(type(k) is str and len(k)<=128);_bounded_result(x,depth+1,budget)
        return
    raise ValueError('ENGINE_RESULT_PLAIN_DATA')


def _metric(v):
    _closed(v,'n brier_sum log_loss accuracy ece_top_label reliability class_counts'.split())
    _count(v['n']);_need(v['n']>0)
    _number(v['brier_sum'],0,2);_number(v['log_loss'],0,-math.log(1e-15))
    for k in ('accuracy','ece_top_label'):_number(v[k],0,1)
    _closed(v['class_counts'],('BREAKOUT','BOUNCE','TIMEOUT'))
    for n in v['class_counts'].values():_count(n)
    _need(sum(v['class_counts'].values())==v['n'])
    bins=v['reliability'];_need(type(bins) is list and 1<=len(bins)<=10)
    seen=set();total=0;correct=0.;ece=0.
    for b in bins:
        _closed(b,('bin','n','confidence','accuracy'));_count(b['bin'],9);_count(b['n'])
        _need(b['n']>0 and b['bin'] not in seen);seen.add(b['bin']);total+=b['n']
        _number(b['confidence'],0,1);_number(b['accuracy'],0,1)
        # A mean of valid bin members can round just below its lower bound.
        # This tolerance covers binary64 averaging, not a different bin width.
        _need(b['bin']/10-1e-12<=b['confidence']<=(b['bin']+1)/10+1e-12)
        _need(math.isclose(b['n']*b['accuracy'],round(b['n']*b['accuracy']),abs_tol=1e-8))
        correct+=b['n']*b['accuracy'];ece+=b['n']*abs(b['confidence']-b['accuracy'])
    _need(total==v['n'] and math.isclose(correct/total,v['accuracy'],abs_tol=1e-8) and math.isclose(ece/total,v['ece_top_label'],abs_tol=1e-8))
    return {k:v[k] for k in ('n','brier_sum','log_loss','accuracy','ece_top_label','class_counts')}


def _errors(v):
    _closed(v,('baseline','graph'))
    out={k:_metric(x) for k,x in v.items()}
    _need(out['baseline']['n']==out['graph']['n'] and out['baseline']['class_counts']==out['graph']['class_counts'])
    return out


def _scenario(v,c,scenario,window=None):
    _closed(v,'net_pnl fees trades profit_factor closed_trade_drawdown refused wait expectancy results fills_scope mfe_mae funding partial_fills'.split())
    for k,expected in (('fills_scope','MODELED_OHLC_NOT_ACTUAL_EXCHANGE'),('mfe_mae','UNAVAILABLE_INTRABAR_PATH'),('funding','EXPLICIT_SYNTHETIC_ZERO_ASSUMPTION'),('partial_fills','UNSUPPORTED')):_need(v[k]==expected)
    for k in ('trades','refused','wait'):_count(v[k])
    for k in ('net_pnl','fees','closed_trade_drawdown'):_number(v[k])
    _need(v['fees']>=0 and 0<=v['closed_trade_drawdown']<=1)
    for k in ('expectancy','profit_factor'):
        if v[k] is not None:_number(v[k]);_need(k!='profit_factor' or v[k]>=0)
    rows=v['results'];_need(type(rows) is list and 1<=len(rows)<=256)
    counts={'SIMULATED':0,'REFUSED':0,'WAIT':0};trades=[];reasons={}
    for row in rows:
        _need(type(row) is dict and row.get('status') in counts);status=row['status'];counts[status]+=1
        if status!='SIMULATED':
            _closed(row,('status','reason'));_need(type(row['reason']) is str and re.fullmatch('[A-Z][A-Z0-9_]{0,127}',row['reason']) is not None)
            reasons[row['reason']]=reasons.get(row['reason'],0)+1
            continue
        _closed(row,'status trade strategy_id simulator_sha256 binding_scope funding depth_partial_fills cost_scenario risk_scope'.split())
        _need(row['strategy_id']==c['strategy_id'] and row['simulator_sha256']==_NATIVE_SHA and row['binding_scope']==_SCOPE and row['cost_scenario']==scenario)
        _need(row['funding']=='SYNTHETIC_ZERO_ASSUMPTION_NOT_OBSERVED' and row['depth_partial_fills']=='UNSUPPORTED' and row['risk_scope']=='EX_ANTE_STOP_ESTIMATE_NOT_GAP_LOSS_GUARANTEE')
        t=row['trade'];_closed(t,'net_pnl gross_pnl fees entry_time exit_time entry_price exit_price side exit_reason metadata'.split())
        for k in ('net_pnl','gross_pnl','fees','entry_price','exit_price'):_number(t[k])
        _need(t['fees']>=0 and min(t['entry_price'],t['exit_price'])>0)
        for k in ('entry_time','exit_time'):_count(t[k],2**53-1)
        _need(t['entry_time']<=t['exit_time'] and t['side'] in ('long','short') and t['exit_reason'] in ('SL','TP','SL_GAP','TP_GAP','EOD'))
        _closed(t['metadata'],('strategy_id','example_id','scope'))
        _need(t['metadata']['strategy_id']==c['strategy_id'] and t['metadata']['scope']=='SYNTHETIC_SCENARIO')
        example=t['metadata']['example_id'];_need(type(example) is str and example.startswith('TOYUSDT:') and example[8:].isdigit())
        cutoff=int(example[8:]);_count(cutoff,2**53-1)
        label_end=((cutoff+59999)//60000)*60000+c['horizon']*60000
        _need(cutoff+c['execution']['latency_ms']<=t['entry_time']<=t['exit_time']<label_end)
        _need(t['entry_time']%60000==0 and t['exit_time']%60000==0)
        if window is not None:
            lo,hi=window
            _need(lo<=cutoff and label_end<=hi and lo<=t['entry_time']<=t['exit_time']<hi)
        _need(math.isclose(t['net_pnl'],t['gross_pnl']-t['fees'],abs_tol=1e-8))
        trades.append(t)
    _need([counts[k] for k in ('SIMULATED','REFUSED','WAIT')]==[v[k] for k in ('trades','refused','wait')])
    _need(math.isclose(sum(t['net_pnl'] for t in trades),v['net_pnl'],abs_tol=1e-8) and math.isclose(sum(t['fees'] for t in trades),v['fees'],abs_tol=1e-8))
    capital=peak=c['capital_usd'];dd=0.
    for t in trades:
        capital+=t['net_pnl'];peak=max(peak,capital);dd=max(dd,(peak-capital)/peak)
    _need(math.isclose(dd,v['closed_trade_drawdown'],abs_tol=1e-8))
    if not trades:_need(v['expectancy'] is None and v['profit_factor'] is None)
    else:
        _need(v['expectancy'] is not None and math.isclose(v['expectancy'],v['net_pnl']/len(trades),abs_tol=1e-8))
        loss=-sum(min(t['net_pnl'],0.) for t in trades);win=sum(max(t['net_pnl'],0.) for t in trades)
        _need(v['profit_factor'] is None if loss==0 else v['profit_factor'] is not None and math.isclose(v['profit_factor'],win/loss,abs_tol=1e-8))
    return {**{k:v[k] for k in ('net_pnl','fees','trades','profit_factor','closed_trade_drawdown','refused','wait','expectancy')},'reason_counts':reasons}


def inspect_engine_result(path,expected_raw_sha256,source_head):
    """Inspect exact existing result bytes; project bounded facts, never authenticate.

    No sibling model/dataset reads, owner imports, runtime calls or UI adoption.
    The raw source digest refers to the input file, never this output itself.
    """
    _sha(expected_raw_sha256,64);_sha(source_head,40);p=_safe(path)
    with p.open('rb') as f:
        st=os.fstat(f.fileno());_need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and 0<st.st_size<=1024*1024)
        raw=f.read(1024*1024+1)
    _need(len(raw)<=1024*1024 and hashlib.sha256(raw).hexdigest()==expected_raw_sha256)
    r=_json(raw);_bounded_result(r);_closed(r,_RESULT_KEYS)
    expected={'status':'SYNTHETIC_FINITE_FEEDBACK_COMPLETE','original_final_oos':'NOT_USED_FOR_SELECTION','candidate_state':'RESEARCH_CANDIDATE_ONLY','promotion_allowed':False,'model_registry':'IMMUTABLE_MODEL_ARTIFACT_ONLY_OWNER_REGISTRY_NOT_CONNECTED','math_integration':'PENDING_OWNER_CONTRACT','terminan_integration':'PENDING_OWNER_API','real_data':'NOT_ADMITTED','rl':'BLOCKED_SIMULATOR_FIDELITY_AND_DATA'}
    for k,v in expected.items():_need(r[k]==v and type(r[k]) is type(v))
    cfg=r['config'];_closed(cfg,_CONFIG_KEYS)
    for k in ('dataset_id','source_hash','simulator_sha256'):_sha(cfg[k],64)
    _need(cfg['source_head']==source_head and cfg['simulator_sha256']==_NATIVE_SHA and cfg['binding_scope']==_SCOPE)
    _need(cfg['schema']=='mwi.synthetic.finite-cycle.v1' and cfg['development_only'] is True and cfg['promotion_allowed'] is False)
    _need(type(cfg['max_candidates']) is int and cfg['max_candidates']==6 and type(cfg['max_iterations']) is int and cfg['max_iterations']==2)
    _count(cfg['policy_holdout_bars'],10000);_count(cfg['policy_holdout_seed'],2**31-1);_count(cfg['policy_holdout_start_ms'],2**53-1)
    _need(cfg['policy_holdout_bars']>0)
    cs=r['candidates'];_need(type(cs) is list and 1<=len(cs)<=6)
    _count(r['evaluated_candidates'],6);_need(r['evaluated_candidates']==len(cs))
    _count(r['iterations'],2);summaries=[];ids={};models=set()
    for item in cs:
        _closed(item,('strategy','base','stress','evaluation_scope'));c=item['strategy'];validate(c)
        _need(c['dataset_id']==cfg['dataset_id'] and c['strategy_id'] not in ids and item['evaluation_scope']=='DEVELOPMENT_ONLY_NOT_FINAL_OOS')
        ids[c['strategy_id']]=c;models.add(c['model_hash'])
        summaries.append({'local_candidate_id':c['strategy_id'],'parent_id':c['parent_id'],'version':c['version'],'family':c['family'],'threshold':c['threshold'],'horizon_bars':c['horizon'],'model_set_hash':c['model_hash'],'base':_scenario(item['base'],c,'BASE'),'stress':_scenario(item['stress'],c,'STRESS')})
    _need(r['iterations']==max(c['version'] for c in ids.values()) and len(models)==1)
    for c in ids.values():_need(c['parent_id'] is None or c['parent_id'] in ids and ids[c['parent_id']]['version']<c['version'])
    _need(r['selected_strategy_id'] in ids);chosen=ids[r['selected_strategy_id']]
    errors=_errors(r['forecast_errors'])
    for item in cs:
        _need(len(item['base']['results'])==errors['baseline']['n']==len(item['stress']['results'])==errors['graph']['n'])
    h=r['policy_holdout'];_closed(h,'seed dataset_id start_ms end_ms selection_used_holdout frozen_strategy_id scope base stress forecast_errors'.split())
    _sha(h['dataset_id'],64);_count(h['start_ms'],2**53-1);_count(h['end_ms'],2**53-1)
    _need(type(h['seed']) is int and h['seed']==cfg['policy_holdout_seed'] and h['start_ms']==cfg['policy_holdout_start_ms'] and h['end_ms']-h['start_ms']==cfg['policy_holdout_bars']*60000)
    _need(h['selection_used_holdout'] is False and h['frozen_strategy_id']==chosen['strategy_id'] and h['scope']=='FRESH_SYNTHETIC_REALIZATION_NOT_EMPIRICAL_MARKET_OOS' and h['dataset_id']!=cfg['dataset_id'])
    hold_errors=_errors(h['forecast_errors']);hold_base=_scenario(h['base'],chosen,'BASE',(h['start_ms'],h['end_ms']));hold_stress=_scenario(h['stress'],chosen,'STRESS',(h['start_ms'],h['end_ms']))
    _need(len(h['base']['results'])==hold_errors['baseline']['n']==len(h['stress']['results'])==hold_errors['graph']['n'])
    out=build_learning_lab_preview(list(ids.values()),expected_raw_sha256,source_head=source_head)
    out.pop('preview_sha256');out['schema']='mwi.local.learning-lab-result-inspection.v1'
    out['artifact_hash_verification']='EXACT_INPUT_RAW_SHA256_MATCH_NOT_AUTHENTICATION'
    out['input_result']={'raw_sha256':expected_raw_sha256,'byte_count':len(raw),'producer_schema':cfg['schema'],'source_head':source_head}
    def reported(data):return {'status':'REPORTED_SYNTHETIC_UNATTESTED','data':data,'missingness':'PARTIAL_LOCAL_RESULT_ONLY','coverage':{'scope':'BOUNDED_EXISTING_RESULT_FILE','count':len(data) if type(data) is list else 1,'has_more':None,'completeness':'NOT_EVALUATED'}}
    d=out['domains']
    for value in d.values():value['coverage']={'scope':'INPUT_RESULT_ONLY','count':None,'has_more':None,'completeness':'UNKNOWN'}
    for key in ('training_progress','forecast_probabilities','mwi_graph_visualizations'):
        d[key]['status']='UNKNOWN';d[key]['data']=None
    d['training_progress']['missingness']='NO_JOB_BINDING_OR_OBSERVATION_CLOCK_IN_RESULT'
    d['forecast_probabilities']['missingness']='AGGREGATE_ERRORS_ARE_NOT_DECISION_PROBABILITIES'
    d['mwi_graph_visualizations']['missingness']='NO_GRAPH_NODES_EDGES_OR_TYPED_PORTS_IN_RESULT'
    d['dataset_readiness']=reported({'local_dataset_id':cfg['dataset_id'],'revision':None,'readiness':'UNKNOWN','training_eligible':False,'requested_coverage':None,'observed_coverage':None,'gaps':None,'reason':'RESULT_FILE_HAS_NO_PRIMARY_DATA_READINESS_EVIDENCE'})
    d['model_versions']=reported([{'model_set_hash':next(iter(models)),'algorithm_version':None,'source_hash_context':cfg['source_hash'],'state':'LOCAL_CANDIDATE_NOT_ADOPTED','limitation':'FITTED_MODEL_ARTIFACT_NOT_READ'}])
    d['strategy_candidates']=reported([{k:v for k,v in x.items() if k not in ('base','stress')} for x in summaries])
    d['simulated_pnl_and_risk']=reported(summaries)
    d['simulated_pnl_and_risk']['semantics']={'scope':'MODELED_SYNTHETIC_OHLC_NOT_LEDGER_OR_REALIZED_BALANCE','currency':'USD_NOTIONAL_AS_DECLARED_BY_STRATEGY','fees':'NATIVE_MODEL_FEE_RATE','slippage':'BASE_2_STRESS_8_BPS','funding':'SYNTHETIC_ZERO_ASSUMPTION','drawdown':'CLOSED_TRADE_EQUITY_ONLY','partial_fills':'UNSUPPORTED','mfe_mae':'UNAVAILABLE'}
    d['oos_results']=reported({'scope':h['scope'],'dataset_id':h['dataset_id'],'seed':h['seed'],'start_ms':h['start_ms'],'end_ms':h['end_ms'],'clock_unit':'UTC_EPOCH_MS','split_ref_kind':'PRODUCER_DECLARED_FRESH_SYNTHETIC_POLICY_HOLDOUT','frozen_strategy_id':h['frozen_strategy_id'],'selection_used_holdout':False,'evaluation_as_of_ms':None,'decision_feature_availability_clocks':None,'metrics':hold_errors,'base':hold_base,'stress':hold_stress,'metric_definitions':{'brier_sum':'SUM_SQUARED_CLASS_ERRORS_UNITLESS','log_loss':'NATURAL_LOG_LOSS','accuracy':'FRACTION','ece_top_label':'FRACTION'},'caveat':'NO_EMPIRICAL_MARKET_OOS_OR_PER_DECISION_CLOCK_EVIDENCE'})
    d['experiment_lineage']=reported({'owner_experiment_id':None,'owner_job_id':None,'source_head':source_head,'source_hash_context':cfg['source_hash'],'dataset_id':cfg['dataset_id'],'model_set_hash':next(iter(models)),'selected_strategy_id':chosen['strategy_id'],'input_result_raw_sha256':expected_raw_sha256,'input_result_bytes':len(raw),'development_errors':errors,'owner_registry':'NOT_CONNECTED'})
    out['limitations'].append('STRICT_RESULT_INTEGRITY_NOT_SEMANTIC_REEXECUTION_OR_OWNER_ADOPTION')
    # This digest is canonical content integrity, not the output file's raw digest.
    out['preview_content_sha256']=_hash(out)
    return out
