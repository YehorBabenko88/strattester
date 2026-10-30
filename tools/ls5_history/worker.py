"""F1 bounded public history candidate. Physical execution requires separate approval."""
import hashlib,importlib.metadata,importlib.util,json,os,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=Path(r'C:\Users\LS-5\Strattester-Physical-Test\DataFirst-11b6c79')
FROOT=ROOT/'F1-History-11b6c79'
RUN=FROOT/'attempt-0001'
BATCH=FROOT/'batch-0001'
NETWORK=None

def safe(path):
    path=Path(path)
    for node in (path,*path.parents):
        if node.exists() and (node.is_symlink() or getattr(node.lstat(),'st_file_attributes',0)&0x400):raise ValueError('LINKED_PATH')
    return path.resolve()

def guard(event,args):
    if event.startswith('socket.'):
        if NETWORK is None:raise RuntimeError('NETWORK_NOT_ADMITTED')
        return NETWORK.audit(event,args)
    if event in ('os.truncate','os.link','os.symlink','os.chmod','os.utime','os.chown','os.lchown','os.fchmod','os.fchown','os.setxattr','os.removexattr'):raise RuntimeError('UNSUPPORTED_MUTATION_DENIED')
    if event in ('subprocess.Popen','os.system','os.startfile','os.exec','os.spawn','os.posix_spawn'):raise RuntimeError('OFFLINE_OPERATION_DENIED')
    if event=='import' and args[0].split('.')[0] in ('torch','psycopg','psycopg2','asyncpg'):raise RuntimeError('MODULE_DENIED')
    if event in ('sqlite3.load_extension','sqlite3.enable_load_extension'):raise RuntimeError('SQLITE_EXTENSION_DENIED')
    if event=='sqlite3.connect':
        allowed=str(BATCH/'history.sqlite3')
        readonly={(FROOT/('batch-'+str(i).zfill(4))/'history.sqlite3').as_uri()+'?mode=ro' for i in range(1,int(BATCH.name[-4:])+1)}
        if not isinstance(args[0],(str,os.PathLike)):raise RuntimeError('SQLITE_SCOPE')
        value=os.fspath(args[0])
        if value.startswith('file:'):
            if value not in readonly:raise RuntimeError('SQLITE_SCOPE')
        elif safe(value)!=BATCH/'history.sqlite3':raise RuntimeError('SQLITE_SCOPE')
    if event=='open':
        mode=args[1] or '';flags=args[2] or 0
        if any(c in mode for c in 'wax+') or flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            if not isinstance(args[0],(str,bytes,os.PathLike)) or not writable(safe(args[0])):raise RuntimeError('WRITE_PATH_DENIED')
    if event in ('os.mkdir','os.remove','os.rmdir','os.rename'):
        for arg in args[:2] if event=='os.rename' else args[:1]:
            if not writable(safe(arg)):raise RuntimeError('MUTATION_PATH_DENIED')

def writable(path):
    return path.is_relative_to(RUN) or path.is_relative_to(BATCH) or path in {FROOT/'session.lock',FROOT/'session-state.json',FROOT/'session-state.json.partial'}

def pin(path,sha):
    path=safe(path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('SHA_MISMATCH')


EXPECTED_STAGES=['interpreter_ready', 'integrity_started', 'integrity_completed', 'collector_started', 'network_admitted', 'collector_completed', 'checkpoint_verified', 'rate_verified', 'result_published', 'worker_completed']

def load(name):
    spec=importlib.util.spec_from_file_location('pinned_'+name,HERE/(name+'.py'))
    value=importlib.util.module_from_spec(spec);sys.modules[spec.name]=value;spec.loader.exec_module(value);return value

def main(ctx):
    global NETWORK
    if len(sys.argv)!=3 or sys.argv[1]!=str(RUN) or sys.version_info[:3]!=(3,12,10):raise ValueError('EXECUTION_SCOPE')
    if not RUN.is_dir() or {p.name for p in RUN.iterdir()}-{'stdout.log','stderr.log','batch-config.json'}:raise ValueError('RUN_NOT_NEW_EMPTY')
    nonce=sys.argv[2];safe(RUN);sys.addaudithook(guard)
    seq=0;started_ns=time.monotonic_ns();started=time.monotonic()
    def mark(stage):
        nonlocal seq
        if seq>=len(EXPECTED_STAGES) or stage!=EXPECTED_STAGES[seq]:raise ValueError('MARKER_ORDER')
        seq+=1;row=dict(seq=seq,stage=stage,pid=os.getpid(),nonce=nonce,cpu_seconds=time.process_time(),wall_seconds=time.monotonic()-started)
        with (RUN/'worker-markers.jsonl').open('a') as f:f.write(json.dumps(row,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())
        ctx.durable(row)
    mark('interpreter_ready');mark('integrity_started');ctx.phase('runtime_integrity')
    pins=json.loads((HERE/'PINS.json').read_text())
    pin(ROOT/'SOURCE_MANIFEST.json',pins['source_manifest_sha256']);pin(ROOT/'DEPENDENCIES.json',pins['dependency_sha256']);pin(ROOT/'evidence/stage-a-created-files-sha256.json',pins['created_index_sha256'])
    manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text())
    if manifest['head']!=pins['head'] or manifest['tree']!=pins['tree'] or len(manifest['files'])!=200:raise ValueError('SOURCE_IDENTITY')
    if {p.relative_to(ROOT/'runtime').as_posix() for p in (ROOT/'runtime').rglob('*') if p.is_file()}!={r['file'] for r in manifest['files']}:raise ValueError('SOURCE_ROSTER')
    for row in manifest['files']:
        path=safe(ROOT/'runtime'/row['file'])
        if not path.is_relative_to(ROOT/'runtime'):raise ValueError('SOURCE_ESCAPE')
        pin(path,row['sha256'])
    ctx.phase('package_integrity')
    entries=[r for r in json.loads((ROOT/'evidence/stage-a-created-files-sha256.json').read_text()) if r['file'].startswith('venv/')]
    for row in entries:
        path=safe(ROOT/row['file'])
        if not path.is_relative_to(ROOT/'venv'):raise ValueError('PACKAGE_ESCAPE')
        pin(path,row['sha256'])
    if {p.relative_to(ROOT).as_posix() for p in (ROOT/'venv').rglob('*') if p.is_file()}!={r['file'] for r in entries}:raise ValueError('PACKAGE_ROSTER')
    sys.path[:0]=[str(ROOT/'runtime'),str(ROOT/'venv/Lib/site-packages')]
    found={d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions(path=[str(ROOT/'venv/Lib/site-packages')])}
    wanted={d['name'].lower().replace('_','-'):d['version'] for d in json.loads((ROOT/'DEPENDENCIES.json').read_text())}
    if found!=wanted or len(found)!=8:raise ValueError('PACKAGE_VERSIONS')
    mark('integrity_completed');ctx.phase('module_admission')
    config=json.loads((RUN/'batch-config.json').read_text())
    n=int(RUN.name[-4:])
    if config['batch_index']!=n:raise ValueError('BATCH_CONFIG')
    sys.path.insert(0,str(HERE))
    import history_collector as collector,history_verify as verify,public_core
    http=load('public_http');NETWORK=http.NetworkPolicy()
    import certifi
    previous=None
    if n>1:
        previous=FROOT/('batch-'+str(n-1).zfill(4))/'checkpoint.json'
        prev_run=FROOT/('attempt-'+str(n-1).zfill(4))
        pin(prev_run/'controller.json',config['previous_controller_sha256'])
        receipt=json.loads((prev_run/'controller.json').read_text())
        if receipt['status']!='F1_BATCH_VERIFIED' or receipt['controller_exit_code']!=0 or receipt['final']['ExitCode']!=0 or receipt['final']['CpuSeconds']>15 or receipt['final']['PeakBytes']>512*1024*1024 or receipt['wall_seconds']>90 or receipt['unexpected_descendant']:raise ValueError('PREVIOUS_RESOURCE_ADMISSION')
        pin(prev_run/'result.json',receipt['functional_result_sha256'])
        previous_result=json.loads((prev_run/'result.json').read_text())
        if previous_result['checkpoint_sha256']!=config['previous_checkpoint_sha256']:raise ValueError('PREVIOUS_CHECKPOINT_BINDING')
    requests=[]
    def append(name,value):
        with (RUN/name).open('a') as f:f.write(json.dumps(value,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())
    def record(meta):
        requests.append(meta);append('requests.jsonl',meta)
        append('rate-events.jsonl',dict(sequence=meta['id'],endpoint_id=meta['endpoint_id'],attempt_start_ns=meta['attempt_start_ns'],http_start_ns=meta['http_start_ns'],completed_ns=meta['completed_ns'],duration_ns=meta['duration_ns'],utc_start=meta['observed_start_utc'],http_status=meta['status'],budget_used=meta['budget_used'],budget_limit=20,pid=os.getpid(),nonce=nonce))
    def on_start(row):append('rate-starts.jsonl',dict(row,pid=os.getpid(),nonce=nonce))
    cancelled=lambda:(RUN/'cancel.request').exists()
    limiter=load('strict_rate').StrictSlidingWindow(deadline_ns=started_ns+80_000_000_000,cancel=cancelled)
    rawdir=RUN/'raw';rawdir.mkdir()
    def decode(body):
        with (rawdir/(str(limiter.used)+'.json')).open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())
        return bytes(body)
    transport=http.PublicHTTP(NETWORK,certifi.where(),record,decode,limiter,on_start)
    def fetch(path,params):
        if not NETWORK.enabled:
            NETWORK.resolve();mark('network_admitted')
        raw=transport(path,params);return raw,requests[-1]
    mark('collector_started');ctx.phase('candle_download')
    receipt=collector.run_batch(FROOT,BATCH.name,fetch,previous=previous,previous_sha=config.get('previous_checkpoint_sha256'),cancel=cancelled)
    mark('collector_completed');checkpoint=BATCH/'checkpoint.json';checkpoint_sha=collector.sha(checkpoint)
    verification=verify.verify_checkpoint(checkpoint,checkpoint_sha);mark('checkpoint_verified')
    events=[json.loads(line) for line in (RUN/'rate-events.jsonl').read_text().splitlines()];starts=[json.loads(line) for line in (RUN/'rate-starts.jsonl').read_text().splitlines()]
    rate=load('rate_verify').verify(events,transport.count,os.getpid(),nonce,starts)
    if rate['status']!='RATE_BUDGET_PASS':collector.publish(FROOT/'session-state.json',{'state':'BLOCKED_RATE'});raise ValueError('RATE_BUDGET_FAIL')
    mark('rate_verified');ctx.phase('publication')
    result=dict(status='F1_BATCH_VERIFIED',head=pins['head'],tree=pins['tree'],pid=os.getpid(),nonce=nonce,checkpoint_sha256=checkpoint_sha,batch_index=n,history_state=receipt['status'],coverage=receipt['coverage'],requests=transport.count,rate_budget=rate,verification=verification,strategies='NOT_EXECUTED',real_oos='NOT_AUTHORIZED',physical_g1='NOT_AUTHORIZED',trading='NO-GO')
    with (RUN/'result.partial').open('x') as f:json.dump(result,f,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.rename(RUN/'result.partial',RUN/'result.json')
    with (RUN/'result-sha256.json').open('x') as f:json.dump({'sha256':hashlib.sha256((RUN/'result.json').read_bytes()).hexdigest()},f);f.flush();os.fsync(f.fileno())
    mark('result_published');ctx.phase('success_completion');mark('worker_completed')
if __name__=='__main__':
    try:
        if len(sys.argv)==3:
            import re
            arg=Path(sys.argv[1])
            if arg.parent!=FROOT or not re.fullmatch(r'attempt-[0-9]{4}',arg.name):raise ValueError('ATTEMPT_PATH')
            RUN=arg;BATCH=FROOT/('batch-'+arg.name[-4:])
        if len(sys.argv)!=3 or sys.argv[1]!=str(RUN) or len(sys.argv[2])!=32 or any(c not in '0123456789abcdef' for c in sys.argv[2]):raise ValueError('SCOPE')
        safe(RUN);diagnostics=load('failure_diagnostics')
        ctx=diagnostics.Context(RUN,sys.argv[2],dict(head='11b6c793e6617c3de08e6ca4fa741625c54c1951',tree='f3a7f9858a0ce59f425543b14e8c1d3593a1b8a9',worker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
        code=diagnostics.run_guarded(ctx,lambda:main(ctx))
    except Exception:code=3
    raise SystemExit(code)
