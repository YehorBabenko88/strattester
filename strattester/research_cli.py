from __future__ import annotations
import argparse,json,time,uuid
from pathlib import Path
from strattester.marketdata.bybit_client import BybitClient
from strattester.marketdata.sqlite_store import SQLiteMarketStore
from strattester.persistence.result_store import ResultStore
from strattester.research.runner import ResearchRunner
from strattester.strategies.registry import StrategyRegistry

def _parser():
    p=argparse.ArgumentParser(prog='strattester-research')
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--results-db',type=Path,required=True)
    scope=p.add_mutually_exclusive_group(required=True)
    scope.add_argument('--symbol',action='append')
    scope.add_argument('--universe',choices=('bybit-linear',))
    p.add_argument('--start-ms',type=int,required=True)
    p.add_argument('--end-ms',type=int,required=True)
    p.add_argument('--strategy',action='append',required=True)
    p.add_argument('--fail-fast',action='store_true')
    return p

def main(argv=None,*,registry=None,client=None):
    a=_parser().parse_args(argv)
    registry=registry or StrategyRegistry()
    available={(d.id,d.version):d for d in registry.discover() if d.enabled}
    wanted=[]
    for spec in a.strategy:
        matches=[d for (sid,_),d in available.items() if sid==spec]
        if not matches: raise SystemExit(f'unknown or disabled strategy: {spec}')
        wanted.extend(matches)
    store=SQLiteMarketStore.open(a.db); results=ResultStore.open(a.results_db)
    client=client or BybitClient()
    if a.universe=='bybit-linear':
        instruments=client.fetch_linear_instruments()
    else:
        instruments=[{'symbol':s,'launchTime':str(a.start_ms)} for s in a.symbol]
    runner=ResearchRunner(store,client,clock_ms=lambda:int(time.time()*1000))
    run_id=str(uuid.uuid4()); output=[]
    failures=[]
    try:
        for instrument in instruments:
            symbol=instrument['symbol']
            for definition in wanted:
                try:
                    r=runner.run(definition,instrument,start_ms=a.start_ms,end_ms=a.end_ms)
                    metrics={'fingerprint':r.fingerprint,'output':r.output}
                    results.put(run_id,symbol,r.strategy_id,r.strategy_version,metrics)
                    output.append({'symbol':symbol,'strategy_id':r.strategy_id,'strategy_version':r.strategy_version,'fingerprint':r.fingerprint})
                except Exception as exc:
                    failures.append({'symbol':symbol,'strategy_id':definition.id,'error':str(exc)})
                    if a.fail_fast:
                        raise
    finally:
        results.close(); store.close()
    print(json.dumps({'run_id':run_id,'results':output,'failures':failures},sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
