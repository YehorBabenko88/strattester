"""Fixed child IPC primitive. Protected scheduler provisioning: NOT_IMPLEMENTED.

serve() accepts an operator-constructed admitted DataFirstScheduler. INIT/job
JSON never selects a factory, executable, source root, workspace or network grant.
The raw main deliberately blocks until protected runtime supplies that factory.
"""
import copy,hashlib,json,re,sys
SCHEMA='grid.data-first.process.v1'
MAX_FRAME=1048576
CODES=frozenset(('PROCESS_ADMISSION_REQUIRED','PROCESS_PLATFORM_UNQUALIFIED','PROCESS_ADMISSION_REVOKED','PROCESS_SOURCE_REJECTED','PROCESS_PROTOCOL_REJECTED','PROCESS_LEASE_FENCED','PROCESS_LEASE_UNAVAILABLE','PROCESS_TIMEOUT','PROCESS_MEMORY','PROCESS_CHILD_FAILED','PROCESS_PIPE_EOF','PROCESS_OUTPUT_REJECTED','PROCESS_CLEANUP_UNAVAILABLE','PROCESS_PROVISIONING_NOT_IMPLEMENTED'))
STATES=frozenset(('SYNCING','PARTIAL','READY','RUNNING','COMPLETED','FAILED','BLOCKED','YIELDED'))

class ProtocolError(RuntimeError):
 def __init__(self,code='PROCESS_PROTOCOL_REJECTED'):
  self.code=code if code in CODES else 'PROCESS_PROTOCOL_REJECTED';super().__init__(self.code)

def need(ok,code='PROCESS_PROTOCOL_REJECTED'):
 if not ok:raise ProtocolError(code)

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def hex_value(value,n=64):return type(value) is str and re.fullmatch('[a-f0-9]{'+str(n)+'}',value) is not None

def frame(nonce,sequence,op,body):
 need(hex_value(nonce) and type(sequence) is int and 0<=sequence<2**31 and type(body) is dict)
 raw=canonical(dict(schema=SCHEMA,nonce=nonce,seq=sequence,op=op,body=body))+b'\n';need(len(raw)<=MAX_FRAME);return raw

def read_frame(stream,nonce=None,sequence=0):
 try:
  raw=stream.readline(MAX_FRAME+1);need(type(raw) is bytes and 0<len(raw)<=MAX_FRAME and raw.endswith(b'\n'),'PROCESS_PIPE_EOF' if not raw else 'PROCESS_PROTOCOL_REJECTED')
  def unique(pairs):
   out={}
   for key,value in pairs:need(key not in out);out[key]=value
   return out
  value=json.loads(raw.decode('utf-8'),object_pairs_hook=unique,parse_constant=lambda _:need(False))
  need(type(value) is dict and set(value)=={'schema','nonce','seq','op','body'} and value['schema']==SCHEMA and value['seq']==sequence and hex_value(value['nonce']))
  need(nonce is None or value['nonce']==nonce)
  need(frame(value['nonce'],sequence,value['op'],value['body'])==raw);return value
 except ProtocolError:raise
 except Exception:raise ProtocolError() from None

class _IPCLease:
 def __init__(self,reader,writer):
  self.reader=reader;self.writer=writer;self.sequence=1;self.last=None
  initial=read_frame(reader);need(initial['op']=='INIT' and set(initial['body'])=={'job'} and type(initial['body']['job']) is dict)
  self.nonce=initial['nonce'];self.job=initial['body']['job'];self.request_sha=digest(self.job.get('payload'))
 def _send(self,op,body):self.writer.write(frame(self.nonce,self.sequence,op,body));self.writer.flush()
 def _rpc(self,op,body):
  self._send(op,body);reply=read_frame(self.reader,self.nonce,self.sequence)
  need(reply['op']=='ACK' and set(reply['body'])=={'op','value'} and reply['body']['op']==op and type(reply['body']['value']) is dict)
  self.sequence+=1;return reply['body']['value']
 def _same_job(self,job):
  need(all(job.get(key)==self.job.get(key) for key in ('id','lease_owner','lease_generation')) and digest(job.get('payload'))==self.request_sha)
 def renew(self,job):
  self._same_job(job);value=self._rpc('RENEW',{});need(set(value)=={'valid'} and value['valid'] is True,'PROCESS_LEASE_FENCED');return True
 def publish(self,job,sequence,state,checkpoint):
  self._same_job(job);need(type(sequence) is int and sequence>=1 and state in STATES and type(checkpoint) is dict)
  body=dict(sequence=sequence,state=state,checkpoint=checkpoint);value=self._rpc('CHECKPOINT',body)
  need(set(value)=={'accepted','sha256','state','request_sha256'} and value['accepted'] is True and value['state']==state and value['request_sha256']==self.request_sha and value['sha256']==digest(body),'PROCESS_LEASE_FENCED')
  self.last=dict(sequence=sequence,state=state,sha256=value['sha256']);return copy.deepcopy(value)
 def finish(self):
  need(self.last is not None and self.last['state'] in ('COMPLETED','FAILED','BLOCKED','YIELDED'));self._send('DONE',self.last)
 def error(self,code):
  try:self._send('ERROR',{'code':code if code in CODES else 'PROCESS_CHILD_FAILED'})
  except Exception:pass

def serve(scheduler,expected_source,*,input_stream=None,output_stream=None):
 """Consume one job using existing sync/evaluation code; never a second queue.

 The caller has already performed protected source/workspace/network admission.
 This function cannot construct or authorize a scheduler from serialized input.
 """
 ipc=None
 try:
  ipc=_IPCLease(sys.stdin.buffer if input_stream is None else input_stream,sys.stdout.buffer if output_stream is None else output_stream)
  need(hex_value(expected_source,40),'PROCESS_ADMISSION_REQUIRED')
  from strattester.engine.data_first import DataFirstScheduler
  from strattester.engine.grid_data_first import execute_assigned,validate_assigned
  need(type(scheduler) is DataFirstScheduler,'PROCESS_ADMISSION_REQUIRED')
  validate_assigned(scheduler,ipc.job,expected_source=expected_source)
  prepare=getattr(scheduler,'protected_prepare',None)
  if prepare is not None:
   need(callable(prepare) and getattr(scheduler,'protected_expected_source',None)==expected_source,'PROCESS_ADMISSION_REQUIRED')
   ipc.renew(ipc.job);prepare()
  execute_assigned(scheduler,ipc.job,ipc,expected_source=expected_source)
  ipc.finish();return 0
 except Exception as error:
  if ipc is not None:ipc.error(getattr(error,'code','PROCESS_CHILD_FAILED'))
  return 78

def main():
 # No JSON flag/environment variable can provision the missing protected factory.
 # No application imports or requests/SQLite factories run through this entry.
 ipc=None
 try:
  need(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode and len(sys.argv)==1,'PROCESS_ADMISSION_REQUIRED')
  ipc=_IPCLease(sys.stdin.buffer,sys.stdout.buffer);ipc.error('PROCESS_PROVISIONING_NOT_IMPLEMENTED')
 except Exception:pass
 return 78

if __name__=='__main__':raise SystemExit(main())
