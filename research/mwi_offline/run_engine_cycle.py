"""Finite synthetic developer cycle using the pinned existing pure simulator."""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mwi_offline.simulation_adapter import materialize_binding,bind_existing
from mwi_offline.synthetic import generate
from mwi_offline.feedback import run_cycle


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True);p.add_argument('--source-head',required=True);p.add_argument('--resume',action='store_true')
    args=p.parse_args();output=Path(args.output);capsule=output.with_name(output.name+'-simulator-source')
    start=time.monotonic();cpu=time.process_time()
    if not args.resume:materialize_binding(Path(__file__).resolve().parents[2],capsule)
    binding=bind_existing(capsule)
    result=run_cycle(output,generate(n=4200),binding,args.source_head,resume=args.resume)
    resource={'wall_seconds':time.monotonic()-start,'cpu_seconds':time.process_time()-cpu,'processes':1,'gpu':0,'hard_cpu_quota':False,
              'runtime_scope':'DEVELOPER_SYNTHETIC_PURE_FUNCTION_ONLY','no_provider_or_database':True}
    if not args.resume:(output/'resources.json').write_text(json.dumps(resource,indent=2),encoding='utf8')
    summary={'status':result['status'],'evaluated_candidates':result['evaluated_candidates'],'iterations':result['iterations'],
             'candidates':[{'id':r['strategy']['strategy_id'],'family':r['strategy']['family'],'version':r['strategy']['version'],
                            'threshold':r['strategy']['threshold'],'net_pnl':r['base']['net_pnl'],'stress_net_pnl':r['stress']['net_pnl'],
                            'trades':r['base']['trades'],'drawdown':r['base']['closed_trade_drawdown']} for r in result['candidates']],
             'original_final_oos':result['original_final_oos'],'resources':resource,'real_data':result['real_data']}
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
