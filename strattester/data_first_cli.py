"""Explicit research data orchestration; planning never activates network."""
import argparse
import json
from pathlib import Path
import threading
import signal

NETWORK_PLAN={
 'mode':'PUBLIC_GET_ONLY_RESEARCH',
 'remote_host':'api.bybit.com','remote_port':443,
 'endpoints':['/v5/market/instruments-info','/v5/market/kline','/v5/market/mark-price-kline',
              '/v5/market/index-price-kline','/v5/market/premium-index-price-kline',
              '/v5/market/open-interest','/v5/market/account-ratio'],
 'credentials':'NONE; environment proxy/netrc disabled',
 'history_limitations':['delisted-before-observation universe not supplied by current active discovery',
                        'unknown launch or trading calendar BLOCKED',
                        'funding/trades/microstructure need independent historical contracts'],
 'LS5_CONNECTED_SYNC':'NOT_AUTHORIZED','PHYSICAL_G1':'NOT_AUTHORIZED','TRADING':'NO-GO'}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('plan-connection')
    run=sub.add_parser('run')
    run.add_argument('--root',type=Path,required=True)
    run.add_argument('--start-ms',type=int,required=True)
    run.add_argument('--end-ms',type=int,required=True,help='exclusive close boundary')
    run.add_argument('--category',action='append',choices=('linear','inverse','spot'))
    run.add_argument('--ticks',type=int,default=1)
    run.add_argument('--allow-network',action='store_true',help='does not substitute owner authorization')
    args=p.parse_args(argv)
    if args.command=='plan-connection':print(json.dumps(NETWORK_PLAN,sort_keys=True));return 0
    if not args.allow_network:p.error('explicit --allow-network and separate owner network authorization required')
    if not 1<=args.ticks<=1000 or not 0<=args.start_ms<args.end_ms:p.error('bounded ticks/nonempty interval required')
    root=args.root.expanduser().resolve();categories=tuple(args.category or ('linear',))
    if len(set(categories))!=len(categories):p.error('duplicate category')
    for component in (root,*root.parents):
        if component.exists() and (component.is_symlink() or getattr(component.lstat(),'st_file_attributes',0)&0x400):
            p.error('linked workspace prohibited')
    marker=root/'data-first-owned.json'
    identity={'version':1,'categories':list(categories),'scope':'DEDICATED_RESEARCH_ONLY'}
    if root.exists():
        if not marker.is_file() or json.loads(marker.read_text())!=identity:p.error('existing root is not this dedicated data-first workspace')
    else:
        root.mkdir(parents=True,exist_ok=False)
        with marker.open('x') as stream:json.dump(identity,stream,sort_keys=True)

    from strattester.config import AppConfig
    from strattester.marketdata.store_factory import open_configured_market_store
    from strattester.marketdata.bybit_client import BybitClient,RetryPolicy
    from strattester.engine.data_first import DataFirstScheduler
    from strattester.persistence.data_first_store import DataFirstStateStore
    from strattester.strategies.base import StrategyDefinition
    from strattester.strategies.registry import StrategyRegistry
    from strattester.strategies.builtin.legacy_grid import LegacyGridStrategy
    from strattester.runtime.system_resources import snapshot
    import requests
    stop=threading.Event()
    previous=signal.signal(signal.SIGINT,lambda *_:stop.set())
    registry=StrategyRegistry()
    registry.register(StrategyDefinition(LegacyGridStrategy.id,LegacyGridStrategy.version,
                                        LegacyGridStrategy.requirements,LegacyGridStrategy))
    def client_factory(category):
        session=requests.Session();session.trust_env=False
        return BybitClient(session=session,retry=RetryPolicy(1,0,0),timeout=10)
    def store_factory(category):
        category_root=root/'market'/category
        cfg=AppConfig(root=category_root,data_dir=category_root,results_dir=root/'results',logs_dir=root/'logs',
                      state_dir=root/'state',market_db=category_root/'market.sqlite3',
                      market_shards_dir=category_root/'shards')
        return open_configured_market_store(cfg)
    state=DataFirstStateStore(root/'state'/'data-first.sqlite3')
    scheduler=DataFirstScheduler(state,registry,client_factory,store_factory,categories=categories,
                                 cancel=stop.is_set,snapshot_provider=lambda:snapshot(root))
    try:
        scheduler.discover();scheduler.plan(start_ms=args.start_ms,end_ms=args.end_ms)
        for _ in range(args.ticks):
            if stop.is_set():break
            scheduler.tick()
        jobs=state.jobs()
        print(json.dumps({'jobs':[{'id':j['id'],'state':j['state'],'reason':j['reason']} for j in jobs],
                          'physical_g1':'NOT_AUTHORIZED','trading':'NO-GO'},sort_keys=True))
        return 0 if jobs and all(j['state']=='COMPLETED' for j in jobs) else 2
    finally:signal.signal(signal.SIGINT,previous)

if __name__=='__main__':raise SystemExit(main())
