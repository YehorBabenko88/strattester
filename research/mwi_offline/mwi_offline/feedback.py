"""Finite synthetic experiment procedure; no scheduler, registry service or ledger."""
import hashlib
import copy
import json
import os
import tempfile
import re
from pathlib import Path
import time
from .evaluation import digest,fit,calibrated,probabilities,split_at,metrics
from .features import build_examples
from .strategy import candidates,next_version,validate
from .controlled_search import prepare_search
from .simulation_adapter import simulate_candidate
from .adapter import _read,_json,_bars
from .synthetic import generate


def development_fit(bars):
    built=build_examples(bars);rows=built['examples']
    if not 30<=len(rows)<=256:raise ValueError('DEVELOPMENT_SUPPORT')
    # Calendar bounds derive from the immutable source window, never label eligibility.
    start,end=min(b['open_ms'] for b in bars),max(b['end_ms'] for b in bars);span=end-start
    at=lambda f:int(start+span*f)
    split=split_at(rows,at(.40),at(.50),at(.58),12*60000,max(b['available_ms'] for b in bars))
    models={};predictions={}
    for key in ('baseline','graph'):
        model=fit(split['train'],key);t=calibrated(model,split['calibration'],key)
        models[key]={'fitted':model,'temperature':t,'model_version':digest({'model':model,'temperature':t})}
        predictions[key]=[probabilities(model,r[key],t) for r in split['test']]
    return {'models':models,'predictions':predictions,'examples':split['test'],
            'feature_names':built['feature_names'],'cohort_counts':built['counts'],
            'train_ids_sha256':digest([r['id'] for r in split['train']]),
            'calibration_ids_sha256':digest([r['id'] for r in split['calibration']]),
            'development_end':at(.58),'reserved_original_oos_start':at(.80),'dataset_id':digest(bars)}


def evaluate_candidate(c,development,bars,binding,stress=False):
    key='graph' if c['family']=='graph_probability' else 'baseline'
    rows=development['examples'];ps=development['predictions'][key]
    capital=peak=c['capital_usd'];maximum_dd=0.;results=[];stopped=False
    for e,p in zip(rows,ps):
        if stopped:results.append({'status':'REFUSED','reason':'CLOSED_EQUITY_DRAWDOWN_STOP'});continue
        # Bounded plain owned slice; no full-history repeated materialization.
        context=[b for b in bars if b['symbol']==e['id'].split(':')[0] and e['cutoff']-60000<=b['open_ms']<e['label_end']]
        r=simulate_candidate(c,e,p,context,binding,capital=capital,stress=stress);results.append(r)
        if r['status']=='SIMULATED':
            capital+=r['trade']['net_pnl'];peak=max(peak,capital)
            maximum_dd=max(maximum_dd,(peak-capital)/peak)
            stopped=maximum_dd>=c['max_drawdown']
    trades=[r['trade'] for r in results if r['status']=='SIMULATED']
    wins=sum(max(0.,t['net_pnl']) for t in trades);loss=-sum(min(0.,t['net_pnl']) for t in trades)
    return {'net_pnl':capital-c['capital_usd'],'fees':sum(t['fees'] for t in trades),'trades':len(trades),
            'profit_factor':wins/loss if loss else None,'closed_trade_drawdown':maximum_dd,
            'refused':sum(r['status']=='REFUSED' for r in results),'wait':sum(r['status']=='WAIT' for r in results),
            'expectancy':sum(t['net_pnl'] for t in trades)/len(trades) if trades else None,
            'results':results,'fills_scope':'MODELED_OHLC_NOT_ACTUAL_EXCHANGE','mfe_mae':'UNAVAILABLE_INTRABAR_PATH',
            'funding':'EXPLICIT_SYNTHETIC_ZERO_ASSUMPTION','partial_fills':'UNSUPPORTED'}


def _bytes(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def frozen_policy_controls(strategy,development,bars,binding):
    """One prespecified development-only forecast reassignment diagnostic.

    No fitting/selection/holdout access. Base and stress reuse the same existing
    simulator binding. A WAIT/rule or unchanged reassignment is uninformative.
    This is an exploratory alignment control, not a significance test.
    """
    validate(strategy)
    key='graph' if strategy['family']=='graph_probability' else 'baseline'
    rows=development['examples'];ps=development['predictions'][key]
    if type(rows) is not list or type(ps) is not list or not 1<=len(rows)==len(ps)<=256:raise ValueError('CONTROL_BUDGET')
    shifted=ps[1:]+ps[:1]
    result=dict(schema='mwi.frozen-policy-control.v1',strategy_id=strategy['strategy_id'],
                status='CONTROL_UNINFORMATIVE',scope='DEVELOPMENT_ONLY_NOT_HOLDOUT',
                kind='CIRCULAR_FORECAST_REASSIGNMENT_OFFSET1',max_control_policies=1,
                max_cost_scenarios=2,used_for_selection=False,refit=False,promotion_allowed=False,
                original_predictions_hash=digest(ps),reassigned_predictions_hash=digest(shifted),
                example_ids_hash=digest([r['id'] for r in rows]))
    if strategy['family'] in ('wait','bounce_rule') or shifted==ps:
        return dict(result,reason='POLICY_IGNORES_PROBABILITIES_OR_REASSIGNMENT_UNCHANGED',base=None,stress=None)
    altered=copy.deepcopy(development)
    altered['predictions'][key]=copy.deepcopy(shifted)
    return dict(result,status='EXPLORATORY_CONTROL_REPORTED',reason='FROZEN_POLICY_DIAGNOSTIC_ONLY',
                base=evaluate_candidate(strategy,altered,bars,binding),
                stress=evaluate_candidate(strategy,altered,bars,binding,True))


def publish_checkpoint(root,value):
    """Atomic local stage receipt, not a distributed journal or authenticated seal."""
    with tempfile.NamedTemporaryFile(dir=root,prefix='.checkpoint-',suffix='.tmp',delete=False) as f:
        tmp=Path(f.name);f.write(_bytes(value));f.flush();os.fsync(f.fileno())
    try:os.replace(tmp,root/'checkpoint.json')
    finally:
        if tmp.exists():tmp.unlink()


def run_cycle(directory,bars,binding,source_head,resume=False):
    if type(bars) is not list or not 1<=len(bars)<8200:raise ValueError('TOTAL_INPUT_BAR_BUDGET')
    _bars(bars)
    start=time.monotonic();root=Path(directory)
    if type(source_head) is not str or re.fullmatch('[0-9a-f]{40}',source_head) is None:raise ValueError('SOURCE_CONTEXT')
    module_root=Path(__file__).parent
    source_hash=digest({p.name:hashlib.sha256(_read(p)).hexdigest() for p in sorted(module_root.glob('*.py'))})
    config={'schema':'mwi.synthetic.finite-cycle.v1','dataset_id':digest(bars),'source_head':source_head,
            'source_hash':source_hash,'simulator_sha256':binding['source_sha256'],'binding_scope':binding['scope'],
            'max_candidates':6,'max_iterations':2,'development_only':True,'promotion_allowed':False,
            'policy_holdout_seed':20261113,'policy_holdout_bars':1800,
            'policy_holdout_start_ms':max(b['end_ms'] for b in bars)+13*60000}
    if resume:
        checkpoint=_json(_read(root/'checkpoint.json'))
        if type(checkpoint) is not dict or set(checkpoint)!={'config','status','artifacts','result_sha256'} or checkpoint['config']!=config or checkpoint['status'] not in ('IN_PROGRESS','COMPLETE'):raise ValueError('RESUME_IDENTITY')
        inventory=checkpoint['artifacts']
        if type(inventory) is not dict or not 1<=len(inventory)<=32 or set(p.name for p in (root/'artifacts').iterdir())!=set(inventory):raise ValueError('RESUME_CLOSED_INVENTORY')
        if 'config.json' not in inventory:raise ValueError('RESUME_REQUIRED_CONFIG')
        for name,pin in checkpoint['artifacts'].items():
            if type(name) is not str or Path(name).name!=name or type(pin) is not str or re.fullmatch('[0-9a-f]{64}',pin) is None or hashlib.sha256(_read(root/'artifacts'/name)).hexdigest()!=pin:raise ValueError('ARTIFACT_TAMPER')
        if checkpoint['status']=='COMPLETE':
            if not {'config.json','development-models.json','selection.json','policy-holdout.json','result.json'}<=set(inventory) or checkpoint['result_sha256']!=inventory['result.json']:raise ValueError('RESUME_REQUIRED_RESULT')
            result=_json(_read(root/'artifacts'/'result.json'))
            if result['config']!=config:raise ValueError('RESULT_IDENTITY')
            if not {'search-initial.json','frozen-policy-control.json'}<=set(inventory) or (result['iterations']==2 and 'search-next-version.json' not in inventory):raise ValueError('RESUME_REQUIRED_SEARCH')
            return result
    else:
        root.mkdir();(root/'artifacts').mkdir();checkpoint={'config':config,'status':'IN_PROGRESS','artifacts':{},'result_sha256':None}
    def save(name,value):
        data=_bytes(value);path=root/'artifacts'/name
        if path.exists():
            if _read(path)!=data:raise ValueError('IMMUTABLE_ARTIFACT_COLLISION')
        else:
            with path.open('xb') as stream:stream.write(data)
        checkpoint['artifacts'][name]=hashlib.sha256(data).hexdigest()
        publish_checkpoint(root,checkpoint)
    save('config.json',config)
    dev=development_fit(bars);save('development-models.json',dev)
    generated=candidates(config['dataset_id'],digest(dev['models']))
    admission=prepare_search([generated[i] for i in (0,1,2,4)],4)
    save('search-initial.json',admission)
    batch=admission['candidates'];results=[]
    def measure(c):
        if len(results)>=6 or time.monotonic()-start>60:raise ValueError('FINITE_RESEARCH_BUDGET')
        try:
            base=evaluate_candidate(c,dev,bars,binding);stress=evaluate_candidate(c,dev,bars,binding,True)
        except Exception as exc:
            save('failure-'+c['strategy_id']+'.json',{'strategy_id':c['strategy_id'],'error_type':type(exc).__name__,'stage':'DEVELOPMENT_SIMULATION','promotion_allowed':False})
            raise
        out={'strategy':c,'base':base,'stress':stress,'evaluation_scope':'DEVELOPMENT_ONLY_NOT_FINAL_OOS'}
        save(c['strategy_id']+'.json',out);results.append(out)
    for c in batch:measure(c)
    best=max(results,key=lambda c:(c['base']['net_pnl'],c['strategy']['strategy_id']))
    if best['base']['net_pnl']>0 and best['strategy']['family'] in ('baseline_probability','graph_probability'):
        searched=prepare_search(batch+[next_version(best['strategy'],t) for t in (.70,.80)],6)
        save('search-next-version.json',searched)
        existing={c['strategy_id'] for c in batch}
        for c in searched['candidates']:
            if c['strategy_id'] not in existing:measure(c)
    winner=max(results,key=lambda c:(c['base']['net_pnl'],c['strategy']['strategy_id']))['strategy']
    save('selection.json',{'strategy_id':winner['strategy_id'],'criterion':'MAX_DEVELOPMENT_NET_PNL_TIE_ID',
                           'created_after_label_ms':max(r['label_available'] for r in dev['examples']),
                           'used_original_final_oos':False,'used_policy_holdout':False})
    try:control=frozen_policy_controls(winner,dev,bars,binding)
    except Exception as exc:
        save('failure-control.json',{'strategy_id':winner['strategy_id'],'error_type':type(exc).__name__,
                                    'stage':'FROZEN_DEVELOPMENT_CONTROL','promotion_allowed':False})
        raise
    save('frozen-policy-control.json',control)
    fresh=generate(seed=20261113,n=1800)
    for row in fresh:
        for clock in ('open_ms','end_ms','available_ms'):row[clock]+=config['policy_holdout_start_ms']
    held_rows=build_examples(fresh)['examples']
    if not 10<=len(held_rows) or dev['cohort_counts']['ELIGIBLE']+len(held_rows)>256 or len(bars)+len(fresh)>10000:raise ValueError('TOTAL_DATA_EPISODE_BUDGET')
    held_predictions={k:[probabilities(v['fitted'],r[k],v['temperature']) for r in held_rows] for k,v in dev['models'].items()}
    held_dev={'examples':held_rows,'predictions':held_predictions}
    holdout={'seed':20261113,'dataset_id':digest(fresh),'start_ms':fresh[0]['open_ms'],'end_ms':fresh[-1]['end_ms'],
             'selection_used_holdout':False,'frozen_strategy_id':winner['strategy_id'],
             'scope':'FRESH_SYNTHETIC_REALIZATION_NOT_EMPIRICAL_MARKET_OOS',
             'base':evaluate_candidate(winner,held_dev,fresh,binding),'stress':evaluate_candidate(winner,held_dev,fresh,binding,True),
             'forecast_errors':{k:metrics([r['label'] for r in held_rows],ps) for k,ps in held_predictions.items()}}
    save('policy-holdout.json',holdout)
    errors={key:metrics([r['label'] for r in dev['examples']],ps) for key,ps in dev['predictions'].items()}
    result={'status':'SYNTHETIC_FINITE_FEEDBACK_COMPLETE','config':config,'evaluated_candidates':len(results),
            'iterations':max(r['strategy']['version'] for r in results),'candidates':results,
            'selected_strategy_id':winner['strategy_id'],'policy_holdout':holdout,
            'forecast_errors':errors,'original_final_oos':'NOT_USED_FOR_SELECTION','candidate_state':'RESEARCH_CANDIDATE_ONLY',
            'promotion_allowed':False,'model_registry':'IMMUTABLE_MODEL_ARTIFACT_ONLY_OWNER_REGISTRY_NOT_CONNECTED',
            'math_integration':'PENDING_OWNER_CONTRACT','terminan_integration':'PENDING_OWNER_API',
            'real_data':'NOT_ADMITTED','rl':'BLOCKED_SIMULATOR_FIDELITY_AND_DATA'}
    save('result.json',result);checkpoint['status']='COMPLETE';checkpoint['result_sha256']=checkpoint['artifacts']['result.json'];publish_checkpoint(root,checkpoint)
    return result
