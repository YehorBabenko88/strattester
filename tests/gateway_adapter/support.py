"""Disposable test support; invokes real pinned Meta pure code, no native service."""
import copy,hashlib,importlib.util,json,os,pathlib,stat,sys,types
ROOT=pathlib.Path(__file__).resolve().parents[2]
PINS={'__init__.py':'70d2201e97a9d8b57973b8328ce7e2938e85096035a867aab8b37b35ee1e1883','core.py':'caa15e51394d3c204ecbcf557cd13ce7a6853b5c8005c4d266971f3f14177170','ohlcv_research_adapter.py':'39b165c945f4d5c00fdf96c460d9bf4e34a32c9cb30483d9be6d88f45403a90f'}
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def source_root():return pathlib.Path(os.environ['GATEWAY_META_SOURCE_ROOT'])
def source_revision():
 value=os.environ['GATEWAY_FIXTURE_SOURCE_REVISION']
 if len(value)!=40 or any(c not in '0123456789abcdef' for c in value):raise ValueError('explicit actual fixture source commit required')
 return value

def payload(symbol='BTCUSDT'):
 rows=[dict(event_start_ms=i*60000,event_end_ms=(i+1)*60000,open=o,high=h,low=l,close=c,volume=v) for i,(o,h,l,c,v) in enumerate(((10,12,8,11,3),(10,11,9,10,2),(11,12,10,12,4)))]
 p=dict(schema='meta.ohlcv.research.request.v1',venue='bybit',market_type='linear',symbol=symbol,timeframe='1m',units={'price':'USDT/'+symbol[:-4],'volume':symbol[:-4]},start_ms=0,end_ms=180000,as_of_ms=300000,evidence_class='SYNTHETIC',source=dict(kind='HISTORICAL_BACKFILL',identity='SYNTHETIC_GATEWAY_FIXTURE',source_revision=source_revision(),retrieval_id='fixture_btc_3rows',retrieved_at_ms=240000,raw_sha256=sha(canonical(rows))),rows=rows)
 return seal(p)

def seal(p):
 keys=('venue','market_type','symbol','timeframe','units','start_ms','end_ms','source','evidence_class','rows')
 p['dataset_id']=sha(canonical(dict(schema='meta.ohlcv.dataset.v1',**{k:p[k] for k in keys})));return p

def request():return dict(schema='stratt.gateway.synthetic.research.request.v1-review1',operation='meta.ohlcv.untouched_levels.v1',experiment={'id':'fixture.gateway.btc.levels','revision':'1'},payload=payload(),decision_ms=300000,analysis_now_ms=360000)

def reference(q):
 package=source_root()/'src/meta_analyse';data={name:(package/name).read_bytes() for name in PINS}
 assert all(sha(data[name])==pin for name,pin in PINS.items())
 prefix='_gateway_reference_meta'
 names=[prefix,prefix+'.core',prefix+'.ohlcv_research_adapter']
 try:
  for name,file in zip(names,('__init__.py','core.py','ohlcv_research_adapter.py')):
   m=types.ModuleType(name);m.__file__=str(package/file);m.__package__=prefix
   if file=='__init__.py':m.__path__=[str(package)]
   sys.modules[name]=m;exec(compile(data[file],str(package/file),'exec'),m.__dict__)
  return sys.modules[names[-1]].analyze_ohlcv_research(copy.deepcopy(q['payload']),decision_ms=q['decision_ms'],now_ms=q['analysis_now_ms'])
 finally:
  for name in reversed(names):sys.modules.pop(name,None)

def load_adapter():
 spec=importlib.util.spec_from_file_location('_gateway_adapter_under_test',ROOT/'strattester/research/gateway_adapter.py')
 module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

def copy_source(target):
 folder=pathlib.Path(target)/'src/meta_analyse';folder.mkdir(parents=True)
 for name in PINS:(folder/name).write_bytes((source_root()/'src/meta_analyse'/name).read_bytes())
 return pathlib.Path(target)

def copied_source_admission_diagnostics(root):
 """Closed facts only: never include paths, source bytes or exception messages."""
 result={'schema':'gateway.copied-source-admission.v1','stage':'START',
         'absolute':False,'canonical_identity_equal':False,'pins_match':False,
         'ordinary_single_link_files':False,'ordinary_ancestry':False,'error_class':'NONE'}
 try:
  result['stage']='ROOT_IDENTITY';result['absolute']=root.is_absolute()
  result['stage']='ANCESTRY';package=root/'src/meta_analyse'
  for p in (*reversed(root.parents),root,root/'src',package):
   info=p.lstat()
   if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or (getattr(info,'st_file_attributes',0)&1024):return result
  result['ordinary_ancestry']=True
  result['stage']='CANONICAL_IDENTITY'
  result['canonical_identity_equal']=root.resolve()==root.absolute()
  result['stage']='PINNED_FILES'
  checks=[];ordinary=[]
  for name,pin in PINS.items():
   p=package/name;info=p.lstat()
   safe=stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode) and info.st_nlink==1 and not (getattr(info,'st_file_attributes',0)&1024) and info.st_size<=1048576
   ordinary.append(safe)
   if not safe:return result
   with p.open('rb') as stream:
    opened=os.fstat(stream.fileno())
    if (opened.st_dev,opened.st_ino)!=(info.st_dev,info.st_ino) or opened.st_nlink!=1:return result
    raw=stream.read(1048577)
   checks.append(sha(raw)==pin)
  result['pins_match']=all(checks);result['ordinary_single_link_files']=all(ordinary)
  result['stage']='COMPLETE'
 except (OSError,ValueError,RuntimeError) as exc:
  result['error_class']=type(exc).__name__ if type(exc).__name__ in (
   'OSError','FileNotFoundError','PermissionError','ValueError','RuntimeError') else 'OTHER_CLOSED_ERROR'
 return result
