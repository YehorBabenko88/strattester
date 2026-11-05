import copy,socket
import pytest
from pathlib import Path

@pytest.fixture(autouse=True)
def central_policy_source(monkeypatch):
 # Required explicit cross-repo source dependency; no fake policy or silent skip.
 import os,sys,types
 source=os.environ.get('UNIFIED_SOURCE_ROOT')
 if not source:pytest.fail('UNIFIED_SOURCE_ROOT required for real central policy integration')
 parent=types.ModuleType('unified_system');parent.__path__=[str(Path(source)/'unified_system')]
 monkeypatch.setitem(sys.modules,'unified_system',parent)
 for name in ('data_first_policy','service_bootstrap','data_first_workspace'):
  path=Path(source)/('unified_system/'+name+'.py')
  if not path.is_file():pytest.fail('central policy/workspace source missing: '+name)
  module=types.ModuleType('unified_system.'+name);module.__file__=str(path)
  monkeypatch.setitem(sys.modules,module.__name__,module)
  exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)

def fixture(tmp_path):
 from strattester.strategies.base import StrategyDefinition,strategy_fingerprint
 from strattester.strategies.builtin.legacy_grid import LegacyGridStrategy as S
 fp=strategy_fingerprint(StrategyDefinition(S.id,S.version,S.requirements,S))
 service=tmp_path/'service';service.mkdir();state=service/'state';state.mkdir()
 manifest={'sources':{'strattester':{'commit':'a'*40}}}
 config={'state_root':str(state)}
 cap=dict(schema='unified.data-first-runtime.v1',source_commit='a'*40,strategy_fingerprints=[fp],categories=['linear'],network_scope='BYBIT_PUBLIC_GET_ONLY',workspace_relative='data-first',limits=dict(timeout_seconds=10,ram_limit_mb=128,max_pages=1,max_observations=1000,requests_per_second=2))
 class Grant:
  live=True;profile={'data_first':cap};descriptor={'service_plan':dict(installation_id='install-1',node_id='NODE1',service_name='UnifiedLab_test',service_sid='S-1-5-80-1-2-3-4-5',computer_name='LABHOST',root=str(service),state=str(state))};service_sid='S-1-5-80-1-2-3-4-5';computer_name='LABHOST'
  def require_current(self):return self.live
 return Grant(),lambda g:(copy.deepcopy(config),copy.deepcopy(manifest)),state

def test_real_scheduler_planner_registry_and_sqlite_factories_no_network(tmp_path,monkeypatch):
 from strattester.engine.grid_data_first_factory import build_scheduler
 from strattester.engine.data_first import DataFirstScheduler
 from strattester.marketdata.history_planner import HistoryPlanner
 def deny(*a,**kw):raise AssertionError('network denied')
 monkeypatch.setattr(socket.socket,'connect',deny)
 grant,readmit,state=fixture(tmp_path);scheduler=build_scheduler(grant,readmit)
 assert type(scheduler) is DataFirstScheduler and type(scheduler.planner) is HistoryPlanner
 assert scheduler.state.instruments(('linear',))==[]
 assert len(scheduler.registry.discover())==1
 store=scheduler._open_store('linear');store.close()
 assert (state/'data-first'/'market'/'linear').is_dir()
 client=scheduler._client('linear',lambda:False)
 assert client.session.trust_env is False
 with pytest.raises(Exception):client.session.get('https://evil.invalid/v5/market/kline')
 grant.live=False
 with pytest.raises(Exception):scheduler.store_factory('linear')
 with pytest.raises(Exception,match='PROCESS_ADMISSION_REVOKED'):client.fetch_klines('BTCUSDT',0,1)
 client.session.close()

@pytest.mark.parametrize('mutation',[lambda g:g.profile.clear(),lambda g:g.profile['data_first'].update(network_scope='ANY'),lambda g:g.profile['data_first'].update(strategy_fingerprints=['b'*64]),lambda g:g.profile['data_first'].update(workspace_relative='../outside')])
def test_missing_or_invalid_permission_precedes_state_mutation(tmp_path,mutation):
 from strattester.engine.grid_data_first_factory import build_scheduler
 grant,readmit,state=fixture(tmp_path);mutation(grant)
 with pytest.raises(Exception):build_scheduler(grant,readmit)
 assert not list(state.iterdir())


def test_protected_prepare_observes_real_client_response_not_assignment_metadata(tmp_path,monkeypatch):
 import json,requests
 from strattester.engine.grid_data_first_factory import build_scheduler
 calls=[]
 class Response:
  status_code=200
  def iter_content(self,chunk_size):yield json.dumps({'retCode':0,'result':{'category':'linear','list':[{'symbol':'ALPHAUSDT','status':'Trading','launchTime':'0'}],'nextPageCursor':''}}).encode()
  def close(self):pass
 class Cookies:
  def clear(self):pass
 class Session:
  cookies=Cookies();trust_env=True;auth=None
  def get(self,url,**kwargs):calls.append((url,kwargs));return Response()
  def close(self):pass
 monkeypatch.setattr(requests,'Session',Session)
 grant,readmit,state=fixture(tmp_path);scheduler=build_scheduler(grant,readmit)
 scheduler.protected_prepare()
 assert scheduler.state.instruments(('linear',))[0]['metadata']['symbol']=='ALPHAUSDT'
 assert scheduler.state.instruments(('linear',))[0]['history'] is None
 assert len(calls)==1 and calls[0][0]=='https://api.bybit.com/v5/market/instruments-info'
 grant.live=False
 with pytest.raises(Exception):scheduler.protected_prepare()
 assert len(calls)==1


def test_factory_consumed_by_ipc_real_sync_sqlite_and_fixed_registry(tmp_path,monkeypatch):
 # Synthetic public observations and modeled protected kernel, real policy/source
 # registry/planner/SyncEngine/SQLite/IPC. No physical network or PG authority.
 import json,requests,socket
 from strattester.engine.grid_data_first_factory import build_scheduler
 from strattester.engine.grid_data_first_worker import serve
 from tests.engine.test_grid_data_first_worker import Pipe
 calls=[]
 class Response:
  status_code=200
  def __init__(self,data):self.data=data
  def iter_content(self,chunk_size):yield json.dumps(self.data).encode()
  def close(self):pass
 class Cookies:
  def clear(self):pass
 class Session:
  cookies=Cookies();trust_env=True;auth=None
  def get(self,url,**kwargs):
   calls.append(url)
   if url.endswith('instruments-info'):result={'category':'linear','list':[{'symbol':'ALPHAUSDT','status':'Trading','launchTime':'0'}],'nextPageCursor':''}
   else:result={'list':[[str(t),'1','1','1','1','1','1'] for t in (120000,60000,0)]}
   return Response({'retCode':0,'result':result})
  def close(self):pass
 def deny(*a,**kw):raise AssertionError('actual network forbidden')
 monkeypatch.setattr(socket.socket,'connect',deny);monkeypatch.setattr(requests,'Session',Session)
 grant,readmit,state=fixture(tmp_path);scheduler=build_scheduler(grant,readmit)
 scheduler.snapshot_provider=None # No claim of physical resource qualification.
 scheduler.protected_prepare();key=scheduler.plan(start_ms=0,end_ms=180000)[0]
 domain=scheduler.state.get(key)['payload'];domain['blockers']=list(domain['blockers'])
 def no_local_claim(*a,**kw):raise AssertionError('SECOND_QUEUE_AUTHORITY')
 monkeypatch.setattr(scheduler.state,'claim',no_local_claim);monkeypatch.setattr(scheduler.state,'transition',no_local_claim)
 job=dict(id=key,job_type='stratt_data_first_v1',payload=dict(schema='grid.stratt-data-first.v1',source_commit='a'*40,domain=domain,resources=dict(cpu=1.,ram_gb=1.,scratch_gb=1.,input_gb=0.,gpu=False,data_locality=None)),lease_owner='fixture',lease_generation=1)
 pipe=Pipe(job)
 assert serve(scheduler,'a'*40,input_stream=pipe,output_stream=pipe)==0
 assert pipe.written[-1]['op']=='DONE' and pipe.written[-1]['body']['state']=='COMPLETED'
 assert scheduler.state.get(key)['state']=='DISCOVERED'
 assert calls.count('https://api.bybit.com/v5/market/kline')==1

 # Missing historical provenance is never copied from assignment into metadata.
 altered=copy.deepcopy(job);altered['payload']['domain'].update(history_provenance='b'*64,history_fingerprint='c'*64,activity_basis='EXPLICIT_ARCHIVE_INTERVALS')
 count=len(calls);rejected=Pipe(altered)
 assert serve(scheduler,'a'*40,input_stream=rejected,output_stream=rejected)==78
 assert calls[count:]==['https://api.bybit.com/v5/market/instruments-info']
 assert scheduler.state.instruments(('linear',))[0]['history'] is None


def test_child_rejects_unowned_sqlite_namespace_and_marker_revocation(tmp_path):
 from strattester.engine.grid_data_first_factory import build_scheduler
 grant,readmit,state=fixture(tmp_path);root=state/'data-first';root.mkdir();foreign=root/'foreign.sqlite3';foreign.write_bytes(b'FOREIGN')
 with pytest.raises(Exception):build_scheduler(grant,readmit)
 assert list(root.iterdir())==[foreign] and foreign.read_bytes()==b'FOREIGN'

def test_child_live_gate_rejects_changed_workspace_marker_before_store(tmp_path):
 from strattester.engine.grid_data_first_factory import build_scheduler
 grant,readmit,state=fixture(tmp_path);scheduler=build_scheduler(grant,readmit)
 marker=state/'data-first'/'data-first-owned.json';marker.write_bytes(marker.read_bytes()+b' ')
 with pytest.raises(Exception):scheduler.store_factory('linear')
 assert not (state/'data-first'/'market').exists()
