"""Fixed public research factories after central kernel/capsule admission.

No job/environment configuration grants permission. The protected raw dispatcher
supplies the live grant and full existing runtime readmission callback. Cache
writes remain domain data; only Grid IPC receipts publish results.
"""
import stat
from pathlib import Path

class FactoryBlocked(ValueError):pass

def need(value,code='PROCESS_ADMISSION_REQUIRED'):
 if not value:raise FactoryBlocked(code)

def capability(value,manifest):
 # Central raw admission has already admitted this exact dependency source.
 from unified_system.data_first_policy import validate_data_first_grant
 return validate_data_first_grant(value,manifest)

def safe(path):
 path=Path(path);need(path.is_absolute() and '..' not in path.parts and not str(path).startswith(('//',chr(92))))
 for part in (*reversed(path.parents),path):
  try:info=part.lstat()
  except FileNotFoundError:continue
  need(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&1024)
 need(path.resolve(strict=False)==path);return path

PATHS=frozenset(('/v5/market/instruments-info','/v5/market/kline','/v5/market/mark-price-kline','/v5/market/index-price-kline','/v5/market/premium-index-price-kline','/v5/market/open-interest','/v5/market/account-ratio'))

class PublicSession:
 """Only fixed HTTPS public market GETs; no ambient proxy/netrc/session auth."""
 def __init__(self,gate):
  import requests
  self._session=requests.Session();self._session.trust_env=False;self._session.auth=None;self._session.cookies.clear();self.gate=gate
 @property
 def trust_env(self):return self._session.trust_env
 def get(self,url,**kwargs):
  self.gate();need(type(url) is str and url in {'https://api.bybit.com'+p for p in PATHS})
  need(set(kwargs)=={'params','timeout','stream','allow_redirects'} and kwargs['allow_redirects'] is False and kwargs['stream'] is True and kwargs['timeout']==10)
  response=self._session.get(url,**kwargs)
  try:self.gate()
  except Exception:response.close();raise
  return response
 def close(self):self._session.close()

def build_scheduler(grant,readmission):
 """Return an actual existing scheduler, without discovering/copying job metadata.

 Central dispatcher must perform the protected read before importing this module.
 Its callback reuses full capsule/ACL/source/config admission. No constructors run
 until both live revision checks and closed permissions/registry have passed.
 """
 need(grant is not None and not isinstance(grant,dict) and callable(getattr(grant,'require_current',None)) and callable(readmission))
 need(grant.require_current() is True,'PROCESS_ADMISSION_REVOKED')
 config,manifest=readmission(grant)
 need(grant.require_current() is True,'PROCESS_ADMISSION_REVOKED')
 cap=capability(grant.profile.get('data_first'),manifest)
 from strattester.strategies.base import StrategyDefinition,strategy_fingerprint
 from strattester.strategies.registry import StrategyRegistry
 from strattester.strategies.builtin.legacy_grid import LegacyGridStrategy as Strategy
 definition=StrategyDefinition(Strategy.id,Strategy.version,Strategy.requirements,Strategy)
 # The fixed implementation is independently checked against owner allowlist.
 need(strategy_fingerprint(definition) in cap['strategy_fingerprints'],'PROCESS_SOURCE_REJECTED')
 registry=StrategyRegistry();registry.register(definition)
 state=safe(config['state_root']);need(str(state)==grant.descriptor['service_plan']['state'])
 from unified_system.data_first_workspace import admit_data_first_workspace
 workspace=admit_data_first_workspace(grant,manifest);root=workspace.root
 def gate():
  need(grant.require_current() is True,'PROCESS_ADMISSION_REVOKED')
  need(capability(grant.profile.get('data_first'),manifest)==cap,'PROCESS_ADMISSION_REVOKED')
  need(workspace.require_current() is True,'PROCESS_ADMISSION_REVOKED');return True
 gate()
 from strattester.config import AppConfig
 from strattester.marketdata.store_factory import open_configured_market_store
 from strattester.marketdata.bybit_client import BybitClient,RetryPolicy
 from strattester.engine.data_first import DataFirstScheduler
 from strattester.persistence.data_first_store import DataFirstStateStore
 from strattester.runtime.system_resources import snapshot
 def client_factory(category):
  gate();need(category in cap['categories'])
  return BybitClient(base_url='https://api.bybit.com',session=PublicSession(gate),before_request=gate,retry=RetryPolicy(1,0,0),timeout=10)
 def store_factory(category):
  gate();need(category in cap['categories']);market=safe(root/'market'/category)
  for path in (market/'market.sqlite3',market/'shards',root/'results',root/'logs',root/'state'):safe(path)
  cfg=AppConfig(root=root,data_dir=market,results_dir=root/'results',logs_dir=root/'logs',state_dir=root/'state',market_db=market/'market.sqlite3',market_shards_dir=market/'shards')
  gate();return open_configured_market_store(cfg)
 gate();metadata=DataFirstStateStore(safe(root/'state'/'data-first.sqlite3'))
 limits=cap['limits']
 scheduler=DataFirstScheduler(metadata,registry,client_factory,store_factory,categories=tuple(cap['categories']),max_concurrency=1,max_jobs_per_tick=1,max_pages_per_job=min(100,limits['max_pages']),max_observations=limits['max_observations'],requests_per_second=limits['requests_per_second'],max_tick_seconds=limits['timeout_seconds'],lease_ms=min(600000,limits['timeout_seconds']*1000+1000),resource_admission=gate,snapshot_provider=lambda:(gate() and snapshot(root)))
 # No .discover/.plan/.tick/local claim: existing protected metadata must match
 # assignment; absent historical provenance remains rejected by execute_assigned.
 scheduler.protected_expected_source=cap['source_commit']
 scheduler.protected_require_current=gate
 def prepare():gate();scheduler.discover();gate()
 scheduler.protected_prepare=prepare
 return scheduler
