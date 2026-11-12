"""Fixed-protocol, bounded multinomial research comparison; no job control."""
import copy
import hashlib
import json
import math
import random

CLASSES=('BREAKOUT','BOUNCE','TIMEOUT')
CONFIG={'epochs':100,'learning_rate':.08,'l2':.02,'seed':20261112,
        'temperature_grid':[.5,1.,2.], 'model':'regularized_multinomial_linear'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def softmax(values):
    top=max(values);v=[math.exp(max(-700,x-top)) for x in values];total=sum(v)
    return [x/total for x in v]


def fit(rows,key):
    if not rows or len(rows)>256:raise ValueError('TRAIN_SIZE')
    d=len(rows[0][key]);n=len(rows)
    if not 1<=d<=64:raise ValueError('FEATURE_COUNT')
    if any(r['label'] not in CLASSES or len(r[key])!=d or
           any(type(x) not in (int,float) or not math.isfinite(x) for x in r[key]) for r in rows):
        raise ValueError('TRAIN_VALUES')
    mean=[sum(r[key][j] for r in rows)/n for j in range(d)]
    scale=[max(1e-8,math.sqrt(sum((r[key][j]-mean[j])**2 for r in rows)/n)) for j in range(d)]
    xs=[[1.]+[(x-mean[j])/scale[j] for j,x in enumerate(r[key])] for r in rows]
    weights=[[0.]*(d+1) for _ in CLASSES]
    for _ in range(CONFIG['epochs']):
        gradient=[[0.]*(d+1) for _ in CLASSES]
        for r,x in zip(rows,xs):
            p=softmax([sum(w*v for w,v in zip(wc,x)) for wc in weights])
            for c in range(3):
                err=p[c]-int(r['label']==CLASSES[c])
                for j in range(d+1):gradient[c][j]+=err*x[j]/n
        for c in range(3):
            for j in range(d+1):
                weights[c][j]-=CONFIG['learning_rate']*(gradient[c][j]+(CONFIG['l2']*weights[c][j] if j else 0))
    return {'mean':mean,'scale':scale,'weights':weights,'feature_key':key,'config':dict(CONFIG)}


def probabilities(model,values,temperature=1.):
    if len(values)!=len(model['mean']) or not temperature>0:raise ValueError('PREDICT_SHAPE')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('PREDICT_VALUES')
    x=[1.]+[(v-model['mean'][j])/model['scale'][j] for j,v in enumerate(values)]
    return softmax([sum(w*v for w,v in zip(wc,x))/temperature for wc in model['weights']])


def metrics(labels,predictions):
    if not labels or len(labels)!=len(predictions):raise ValueError('METRIC_SHAPE')
    for y,p in zip(labels,predictions):
        if y not in CLASSES or len(p)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in p) or abs(sum(p)-1)>1e-8:
            raise ValueError('METRIC_VALUES')
    n=len(labels);brier=loss=accuracy=0.;bins=[[] for _ in range(10)]
    for y,p in zip(labels,predictions):
        target=CLASSES.index(y);chosen=max(range(3),key=lambda i:p[i]);conf=p[chosen]
        brier+=sum((v-int(i==target))**2 for i,v in enumerate(p))
        loss-=math.log(max(p[target],1e-15));accuracy+=int(chosen==target)
        bins[min(9,int(conf*10))].append((conf,int(chosen==target)))
    reliability=[{'bin':i,'n':len(b),'confidence':sum(x for x,_ in b)/len(b),
                  'accuracy':sum(y for _,y in b)/len(b)} for i,b in enumerate(bins) if b]
    return {'n':n,'brier_sum':brier/n,'log_loss':loss/n,'accuracy':accuracy/n,
            'ece_top_label':sum(b['n']*abs(b['confidence']-b['accuracy']) for b in reliability)/n,
            'reliability':reliability,'class_counts':{c:labels.count(c) for c in CLASSES}}


def split_at(rows,train_end,cal_end,test_end,embargo,evaluation_as_of=None):
    if not 0<=embargo or not train_end<cal_end<test_end:raise ValueError('SPLIT_BOUNDS')
    if evaluation_as_of is None:evaluation_as_of=test_end
    selected={};excluded={}
    for key,lo,hi in (('train',-1,train_end),('calibration',train_end,cal_end),('test',cal_end,test_end)):
        candidates=[r for r in rows if lo<=r['cutoff']<hi]
        good=[r for r in candidates if r['label'] in CLASSES and r['label_available'] is not None
              and max(r['label_end'],r['label_available'])<=evaluation_as_of]
        if key!='test':
            good=[r for r in good if max(r['label_end'],r['label_available'])+embargo<hi]
        selected[key]=good;excluded[key]=len(candidates)-len(good)
    groups=[{r['group_id'] for r in selected[k]} for k in selected]
    if any(groups[i]&groups[j] for i in range(3) for j in range(i+1,3)):raise ValueError('SPLIT_GROUP_OVERLAP')
    selected['excluded']=excluded
    return selected


def block_permute(rows):
    out=copy.deepcopy(rows)
    if len(rows)<4:raise ValueError('CONTROL_SUPPORT')
    # Circular block displacement retains local label runs, with deterministic offset.
    shift=max(1,len(rows)//3)
    labels=[r['label'] for r in rows]
    original=list(labels)
    for step in range(len(rows)):
        offset=(shift+step)%len(rows)
        candidate=original[offset:]+original[:offset]
        if candidate!=original:
            labels=candidate;break
    else:raise ValueError('CONTROL_UNINFORMATIVE')
    for r,y in zip(out,labels):r['label']=y
    return out


def permute_edge_summaries(rows):
    out=copy.deepcopy(rows)
    # TOY_NEAR_ZONE_V2 graph extras: nearest,confluence,degree,edge_distance,count.
    if not out or any(len(r['graph'])!=len(r['baseline'])+5 for r in out):return out
    pairs=[r['graph'][len(r['baseline'])+2:len(r['baseline'])+4] for r in out]
    random.Random(CONFIG['seed']).shuffle(pairs)
    for r,pair in zip(out,pairs):
        d=len(r['baseline']);r['graph'][d+2:d+4]=pair
    return out


def calibrated(model,rows,key):
    if not rows:raise ValueError('CALIBRATION_EMPTY')
    losses=[]
    for t in CONFIG['temperature_grid']:
        losses.append((metrics([r['label'] for r in rows],[probabilities(model,r[key],t) for r in rows])['log_loss'],t))
    return min(losses)[1]


def paired_block_interval(differences,block=3):
    if not differences or not 1<=block<=len(differences):raise ValueError('BOOTSTRAP_SUPPORT')
    rng=random.Random(CONFIG['seed']);n=len(differences);means=[]
    for _ in range(400):
        draw=[]
        while len(draw)<n:
            start=rng.randrange(n)
            draw.extend(differences[(start+j)%n] for j in range(block))
        means.append(sum(draw[:n])/n)
    means.sort()
    return {'mean':sum(differences)/n,'lower':means[9],'upper':means[389],
            'resamples':400,'block_episodes':block,'meaning':'exploratory_paired_circular_block_95pct_percentile_no_iid_or_significance_claim'}


def compare(split):
    train,cal,test=[copy.deepcopy(split[k]) for k in ('train','calibration','test')]
    for r in train+cal+test:
        if 'node_only' not in r:r['node_only']=r['baseline']+r['graph'][len(r['baseline']):]
    if min(map(len,(train,cal,test)))<3:raise ValueError('SPLIT_SUPPORT')
    ys=[r['label'] for r in test];report={};models={};predictions={}
    for name,key in (('baseline','baseline'),('node_only','node_only'),('graph','graph'),('label_permutation','baseline'),('edge_summary_permutation','graph')):
        try:fitting=block_permute(train) if name=='label_permutation' else copy.deepcopy(train)
        except ValueError as exc:
            if str(exc)!='CONTROL_UNINFORMATIVE':raise
            report[name]={'status':'CONTROL_UNINFORMATIVE'};models[name]={'status':'CONTROL_UNINFORMATIVE'};continue
        if name=='edge_summary_permutation':fitting=permute_edge_summaries(train)
        model=fit(fitting,key);t=calibrated(model,cal,key)
        predictions[name]=[probabilities(model,r[key],t) for r in test]
        report[name]={'temperature':t,'uncalibrated':metrics(ys,[probabilities(model,r[key],1.) for r in test]),
                      **metrics(ys,predictions[name])}
        models[name]={'fitted_hash':digest(model),'temperature':t}
    prior=[(1+sum(r['label']==c for r in train))/(3+len(train)) for c in CLASSES]
    predictions['prior']=[prior]*len(test)
    report['prior']=metrics(ys,predictions['prior'])
    losses={name:[sum((v-int(j==CLASSES.index(y)))**2 for j,v in enumerate(p)) for y,p in zip(ys,ps)] for name,ps in predictions.items()}
    uncertainty={}
    for candidate,reference in (('baseline','prior'),('graph','baseline'),('graph','node_only')):
        diffs=[a-b for a,b in zip(losses[candidate],losses[reference])]
        uncertainty[candidate+'_minus_'+reference]=[paired_block_interval(diffs,block=min(b,len(diffs))) for b in (3,6)]
    return {'metrics':report,'models':models,'counts':{k:len(split[k]) for k in ('train','calibration','test')},
            'excluded':split['excluded'],'uncertainty':uncertainty,
            'prediction_artifact':{'ids':[r['id'] for r in test],'labels':ys,'probabilities':predictions},
            'split_ids_hash':{k:digest([r['id'] for r in split[k]]) for k in ('train','calibration','test')}}


def run_evaluation(rows,embargo,evaluation_as_of=None):
    if not rows or len(rows)>256:raise ValueError('EXAMPLE_CAP')
    rows=sorted(rows,key=lambda r:r['cutoff'])
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('DUPLICATE_ID')
    start,end=rows[0]['cutoff'],rows[-1]['cutoff']+1;span=end-start
    if evaluation_as_of is None:evaluation_as_of=max(max(r['label_end'],r['label_available']) for r in rows if r['label_available'] is not None)
    at=lambda f:int(start+span*f)
    folds=[]
    for origin in (.40,.50,.60):
        train_end,cal_end,test_end=at(origin),at(origin+.10),at(origin+.18)
        folds.append({'train_end':train_end,'test_start':cal_end,'test_end':test_end,
                      **compare(split_at(rows,train_end,cal_end,test_end,embargo,evaluation_as_of))})
    final=compare(split_at(rows,at(.65),at(.80),end,embargo,evaluation_as_of))
    final.update(test_start=at(.80),train_end=at(.65),calibration_end=at(.80))
    return {'protocol':'fixed_three_expanding_development_folds_then_final20pct_time_holdout',
            'oos_governance':'protocol_fixed_in_source_not_external_sealing_authority',
            'classes':CLASSES,'config':dict(CONFIG),'embargo':embargo,'evaluation_as_of':evaluation_as_of,
            'decision_window_end_exclusive':end,'folds':folds,'final':final,
            'limitations':['dependent episodes/folds: no iid confidence claim','no hyperparameter tuning on final holdout',
                           'calibration on disjoint calibration block only','synthetic metrics do not establish market edge']}
