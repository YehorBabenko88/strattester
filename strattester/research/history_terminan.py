"""Read-only Terminan/training-review adapter. No execution or fitting capability."""
import html
import math
import uuid
from .grid_math_history import admit, canonical, digest, number

METRICS=('gross_pnl','fees','slippage','funding','net_pnl')

def close(a,b):return number(a) and number(b) and math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9)

def review_packet(result,expected_receipt):
    try:
        raw=canonical(result)
        if len(raw)>8*1024*1024:raise ValueError('RESULT_LIMIT')
        r=result
        if r['schema']!='strattester.terminan.result.v1.1' or r['model_version']!='grid-frozen-analog-v1':raise ValueError('REVIEW_SCHEMA')
        if expected_receipt!=r['completion_receipt'] or digest({k:v for k,v in r.items() if k!='completion_receipt'})!=expected_receipt:raise ValueError('RECEIPT_PIN')
        if any(r[k] is not False for k in ('training_authorized','execution_authority','trading_authorized')):raise ValueError('AUTHORITY')
        expected_state='BLOCKED_SYNTHETIC' if r['evidence_class']=='SYNTHETIC' else 'REQUIRES_INDEPENDENT_OOS_REVIEW'
        if r['training_candidate']!=expected_state or r['source_authenticity']!='REQUIRES_INDEPENDENT_RECEIPT_PROVISIONING':raise ValueError('REVIEW_STATE')
        envelope={'schema':'grid.history.v1.1','request':r['source_request'],'source':r['source'],
          'evidence_class':r['evidence_class'],'rows':r['observations'],'source_receipts':r['source_receipts'],
          'execution_authority':False,'trading_authorized':False,'watermark_ms':r['watermark_ms'],
          'dataset_id':r['dataset_id'],'dataset_fingerprint':r['dataset_fingerprint']}
        d=admit(envelope,r['dataset_fingerprint']);rows=d['rows'];p=r['policy']
        if r['market']!={k:d['request'][k] for k in ('venue','market_type','symbol')}:raise ValueError('MARKET_IDENTITY')
        if r['units']!={'cash':'USDT','price':'USDT/BTC','quantity':'BTC','time':'UTC_MS'}:raise ValueError('UNITS')
        if p.get('model_version')!=r['model_version']:raise ValueError('MODEL_VERSION')
        bounds=[d['request']['start_ms'],p['train_end_ms'],p['validation_end_ms'],p['test_end_ms']]
        if not bounds[0]<bounds[1]<bounds[2]<bounds[3]==d['request']['end_ms']:raise ValueError('SPLITS')
        if len(r['fills'])>2000 or len(r['math_trace'])>2000 or len(r['training_candidates'])>2000:raise ValueError('ROW_LIMIT')
        for name,low,high in zip(('train','validation','test'),bounds,bounds[1:]):
            split=r['splits'][name]
            if (split['start_ms'],split['end_ms'])!=(low,high):raise ValueError('SPLITS')
            fills=[t for t in r['fills'] if t['split']==name]
            if split['trades']!=len(fills):raise ValueError('TRADE_COUNT')
            for key in METRICS:
                if not close(split['metrics'][key],sum(t[key] for t in fills)):raise ValueError('SPLIT_METRICS')
        for key in METRICS:
            if not close(r['metrics'][key],sum(t[key] for t in r['fills'])):raise ValueError('TOTAL_METRICS')
        cash=p['starting_cash'];previous_exit=0;events=[]
        if len(r['equity'])!=len(r['fills']):raise ValueError('EQUITY_COUNT')
        run_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'strattester-history:'+expected_receipt))
        for i,t in enumerate(r['fills']):
            if (t['split'] not in r['splits'] or t['side'] not in (-1,1)
                or any(type(t[k]) is not int for k in ('decision_ms','entry_ms','exit_ms'))
                or not previous_exit<=t['entry_ms']<t['exit_ms'] or t['decision_ms']>t['entry_ms']):raise ValueError('FILL_CHRONOLOGY')
            if any(not number(t[k]) for k in (*METRICS,'entry_price','exit_price','quantity','forecast')):raise ValueError('NONFINITE')
            if min(t['entry_price'],t['exit_price'],t['quantity'],t['forecast'])<=0 or min(t['fees'],t['slippage'])<0:raise ValueError('FILL_NUMERIC')
            low,high=r['splits'][t['split']]['start_ms'],r['splits'][t['split']]['end_ms']
            if not low<=t['entry_ms']<t['exit_ms']<=high:raise ValueError('SPLIT_LABEL')
            if not close(t['net_pnl'],t['gross_pnl']-t['fees']-t['slippage']-t['funding']):raise ValueError('COST_RECONCILIATION')
            cash+=t['net_pnl'];curve=r['equity'][i]
            if curve['timestamp_ms']!=t['exit_ms'] or not close(curve['cash_usdt'],cash):raise ValueError('EQUITY_RECONCILIATION')
            previous_exit=t['exit_ms']
            events.append({'run_id':run_id,'strategy_id':r['strategy'],'symbol':r['market']['symbol'],
              'trade_id':digest({'receipt':expected_receipt,'ordinal':i}),'entry_ms':t['entry_ms'],'exit_ms':t['exit_ms'],
              'entry_price':t['entry_price'],'exit_price':t['exit_price'],'side':'long' if t['side']==1 else 'short',
              'quantity':t['quantity'],'pnl':t['net_pnl']})
        frozen_count=0
        for row in rows:
            if row['event_end_ms']>p['train_end_ms'] or row['available_at_ms']>p['train_end_ms']:break
            frozen_count+=1
        if frozen_count<20 or r['train_count']!=frozen_count:raise ValueError('TRAIN_COUNT')
        trace_by_origin={}
        for trace in r['math_trace']:
            prefix=[x for x in rows if x['event_end_ms']<=trace['feature_event_end_ms']]
            trace_key=(trace['decision_ms'],trace['feature_event_end_ms'])
            if (len(prefix)!=trace['sample_count'] or not prefix or digest(prefix)!=trace['prefix_digest']
                or trace['model_version']!=r['model_version'] or trace_key in trace_by_origin
                or not number(trace['forecast']) or trace['forecast']<=0
                or not number(trace['volatility']) or trace['volatility']<0):raise ValueError('MATH_TRACE')
            if (trace['watermark_ms']!=max(x['watermark_ms'] for x in prefix)
                or trace['feature_available_at_ms']!=max(x['available_at_ms'] for x in prefix)
                or trace['feature_available_at_ms']>trace['decision_ms']):raise ValueError('TRACE_LOOKAHEAD')
            if trace['train_count']!=min(len(prefix),frozen_count):raise ValueError('TRACE_TRAIN_COUNT')
            if trace['forecast_target_event_end_ms']!=prefix[-1]['event_end_ms']+60000:raise ValueError('FORECAST_HORIZON')
            timed_request={'schema':'math.history.request.v1.1','rows':prefix,'dataset_id':d['dataset_id'],
                'dataset_fingerprint':d['dataset_fingerprint'],'source':d['source'],
                'market':r['market'],'units':d['request']['units'],'decision_ms':trace['decision_ms'],
                'train_count':trace['train_count'],'train_end_ms':p['train_end_ms'],
                'max_age_ms':d['request']['max_age_ms'],'model_version':r['model_version']}
            if trace['request_digest']!=digest(timed_request):raise ValueError('TRACE_REQUEST_BINDING')
            trace_by_origin[trace_key]=trace
        by_revision={row['revision']:row for row in rows};seen=set()
        for c in r['training_candidates']:
            row=by_revision[c['label_revision']];key=(c['origin_ms'],c['feature_event_end_ms']);trace=trace_by_origin[key]
            if (c['eligible_for_training'] is not False or c['split']!='test' or key in seen
                or not bounds[2]<=row['event_start_ms']<row['event_end_ms']<=bounds[3]
                or not c['origin_ms']<c['label_event_end_ms']==row['event_end_ms']==trace['forecast_target_event_end_ms']<=c['label_available_at_ms']==row['available_at_ms']
                or c['label_close']!=row['close'] or c['features']!={k:trace[k] for k in ('forecast','volatility')}):raise ValueError('TRAINING_REVIEW_LOOKAHEAD')
            seen.add(key)
        packet={'schema':'terminan.history.review.v1.1','run_id':run_id,'result_receipt':expected_receipt,
          'evidence_class':r['evidence_class'],'strategy':r['strategy'],'market':r['market'],'model':r['math'],
          'model_version':r['model_version'],'evaluation_protocol':r['evaluation_protocol'],
          'source':{'dataset_id':r['dataset_id'],'snapshot_fingerprint':r['dataset_fingerprint'],
             'identity':r['source'],'watermark_ms':r['watermark_ms'],'units':r['units'],
             'source_authenticity':r['source_authenticity'],'receipt_hashes':r['source_receipts']},
          'split_receipts':r['splits'],'oos_metrics':r['splits']['test']['metrics'],'diagnostic_totals':r['metrics'],
          'trade_events':events,'equity':r['equity'],'observations':rows,'math_trace':r['math_trace'],
          'training_review':{'state':r['training_candidate'],'candidates':r['training_candidates']},'warnings':r['warnings'],
          'training_authorized':False,'execution_authority':False,'trading_authorized':False}
        if 'published_at_ms' in r:
            published=r['published_at_ms']
            floor=max(max(x['available_at_ms'] for x in rows),max((t['decision_ms'] for t in r['math_trace']),default=0),r['splits']['test']['end_ms'])
            if type(published) is not int or not floor<=published<=2**53-1:raise ValueError('REVIEW_PUBLICATION_CLOCK')
            packet['published_at_ms']=published
        packet['packet_fingerprint']=digest(packet)
        return packet
    except (KeyError,TypeError,OverflowError,IndexError) as exc:raise ValueError('REVIEW_UNAVAILABLE') from exc


def render_review(result,expected_receipt):
    p=review_packet(result,expected_receipt)
    def esc(x):return html.escape(str(x),quote=True)
    def plot(points,color):
        if not points:return '<p>No observations</p>'
        x0,x1=min(x for x,y in points),max(x for x,y in points);y0,y1=min(y for x,y in points),max(y for x,y in points)
        coords=' '.join(f'{20+860*(x-x0)/max(1,x1-x0):.2f},{170-140*(y-y0)/max(1e-12,y1-y0):.2f}' for x,y in points)
        return f'<svg viewBox="0 0 900 200" role="img" aria-label="Read-only chart"><polyline fill="none" stroke="{color}" stroke-width="2" points="{coords}"/><text x="20" y="195">UTC ms {esc(x0)} → {esc(x1)} · {esc(y0)} → {esc(y1)}</text></svg>'
    metrics=''.join('<tr><td>'+esc(name)+'</td>'+''.join('<td>'+esc(split['metrics'][k])+'</td>' for k in METRICS)+'</tr>' for name,split in p['split_receipts'].items())
    trades=''.join('<tr>'+''.join('<td>'+esc(t[k])+'</td>' for k in ('entry_ms','exit_ms','side','entry_price','exit_price','quantity','pnl'))+'</tr>' for t in p['trade_events'][:100])
    source=p['source'];oos=p['oos_metrics']
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Terminan · Historical research review</title><style>
body{margin:0;background:#101822;color:#e7edf5;font:15px system-ui}main{max-width:1150px;margin:36px auto;padding:24px}header,section{background:#192534;border:1px solid #304255;border-radius:12px;padding:22px;margin-bottom:20px}h1{font-size:30px;margin:8px 0}h2{font-size:19px}p{line-height:1.6}.muted{color:#adbdce}.tag{display:inline-block;background:#533c1e;color:#ffe0a0;padding:7px 12px;border-radius:5px}code,pre{white-space:pre-wrap;overflow-wrap:anywhere}svg{width:100%;background:#111e2b;border-radius:8px}svg text{fill:#aab9ca;font-size:12px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:10px;border-bottom:1px solid #304255;overflow-wrap:anywhere}.scroll{overflow:auto}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}@media(max-width:750px){.grid{display:block}}a{color:#8bd3ca}
</style><main><header><span class="tag">'''+esc(p['evidence_class'])+''' · RESEARCH ONLY</span><h1>Historical research review</h1><p>Grid → Math → Strattester → Terminan</p><p class="muted">Training, execution and trading authority: FALSE. This artifact does not run computations, connect to a service, or promote a model.</p></header>
<section><h2>Strategy & mathematical model</h2><p>'''+esc(p['strategy'])+' · '+esc(p['model_version'])+'''</p><p class="muted">'''+esc(p['evaluation_protocol'])+'''</p><pre>Math commit: '''+esc(p['model']['commit'])+'\nMath tree: '+esc(p['model']['tree'])+'''</pre></section>
<div class="grid"><section><h2>Held-out test</h2><p>Net PnL: <strong>'''+esc(oos['net_pnl'])+''' USDT</strong></p><p>Fees: '''+esc(oos['fees'])+' · Slippage: '+esc(oos['slippage'])+' · Signed funding: '+esc(oos['funding'])+'''</p><p class="muted">Test is held out for model selection. No profitability certification.</p></section><section><h2>Training review</h2><p>'''+esc(p['training_review']['state'])+'''</p><p>Candidate rows: '''+esc(len(p['training_review']['candidates']))+''' · eligible_for_training: FALSE</p><p class="muted">OOS labels are evaluation-only in this run. An independent review is required before any future training use.</p></section></div>
<section><h2>Historical close · USDT/BTC</h2>'''+plot([(r['event_end_ms'],r['close']) for r in p['observations']],'#8bd3ca')+'''<h2>Math forecast at target event end · USDT/BTC</h2>'''+plot([(t['forecast_target_event_end_ms'],t['forecast']) for t in p['math_trace']],'#d3b78b')+'''</section>
<section><h2>Diagnostic cash curve · USDT</h2><p class="muted">Includes train and validation diagnostics. Use the test row below for held-out results.</p>'''+plot([(v['timestamp_ms'],v['cash_usdt']) for v in p['equity']],'#8baad3')+'''</section>
<section class="scroll"><h2>Split receipts · USDT</h2><table><thead><tr><th>Split</th><th>Gross</th><th>Fees</th><th>Slippage</th><th>Funding</th><th>Net</th></tr></thead><tbody>'''+metrics+'''</tbody></table></section>
<section class="scroll"><h2>Simulated trade events · first 100</h2><table><tr><th>Entry UTC ms</th><th>Exit UTC ms</th><th>Side</th><th>Entry</th><th>Exit</th><th>BTC</th><th>Net USDT</th></tr>'''+trades+'''</table></section>
<section><h2>Source & immutable evidence</h2><pre>Dataset ID: '''+esc(source['dataset_id'])+'\nSnapshot: '+esc(source['snapshot_fingerprint'])+'\nSource: '+esc(source['identity'])+'\nWatermark UTC ms: '+esc(source['watermark_ms'])+'\nSource authenticity: '+esc(source['source_authenticity'])+'\nResult receipt: '+esc(p['result_receipt'])+'\nPacket SHA256: '+esc(p['packet_fingerprint'])+'''</pre><p class="muted">Independent pin provisioning is required. Hash integrity does not establish exchange completeness or source authentication.</p></section>
<section><h2>Warnings</h2><pre>'''+esc('\n'.join(p['warnings']))+'''</pre></section></main></html>'''
