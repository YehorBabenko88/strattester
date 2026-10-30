import unittest,tempfile,json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]) if (Path(__file__).resolve().parent.name=='tests') else str(Path(__file__).resolve().parent))
import history_collector as c
import history_verify as v
class Fake:
 def __init__(self):self.calls=[];self.server=1793380560000
 def __call__(self,path,p):
  self.calls.append((path,dict(p)))
  if path.endswith('/time'):data={'result':{'timeNano':str(self.server*1000000)}}
  elif path.endswith('/instruments-info'):data={'result':{'category':'linear','nextPageCursor':'','list':[dict(symbol=s,status='Trading',launchTime='1',contractType='LinearPerpetual',deliveryTime='0') for s in c.SYMBOLS]}}
  else:
   step=60000 if p['interval']=='1' else 300000
   data={'result':{'category':'linear','symbol':p['symbol'],'list':[[str(t),'100','101','99','100','1','100'] for t in reversed(range(p['start'],p['end']+1,step))]}}
  data['retCode']=0;body=json.dumps(data).encode();return body,dict(path=path,params=p,status=200,body_sha256=hashlib.sha256(body).hexdigest(),body_bytes=len(body),observed_start_utc='2026-10-30T17:59:59+00:00',observed_end_utc='2026-10-30T18:00:00+00:00')
class Tests(unittest.TestCase):
 def batch(self,root,name,f,**kw):return c.run_batch(root,name,f,clock_utc_ms=lambda:f.server,cooldown=lambda _:None,**kw)
 def test_partial_resume_no_redownload_and_verifier(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);f=Fake();first=self.batch(root,'batch-0001',f);self.assertEqual(len(f.calls),20);self.assertEqual(first['status'],'PARTIAL');cp=root/'batch-0001/checkpoint.json';pin=c.sha(cp)
   self.assertEqual(v.verify_checkpoint(cp,pin)['history_state'],'PARTIAL')
   second=self.batch(root,'batch-0002',f,previous=cp,previous_sha=pin);self.assertEqual(second['batch_requests'],20)
   ranges=[(p['symbol'],p['interval'],p['start'],p['end']) for path,p in f.calls if path.endswith('/kline')];self.assertEqual(len(ranges),len(set(ranges)));self.assertEqual(c.sha(cp),pin)
 def test_corrupt_checkpoint_cancel_and_lease(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);f=Fake();self.batch(root,'batch-0001',f);cp=root/'batch-0001/checkpoint.json';before=len(f.calls)
   with self.assertRaises(ValueError):self.batch(root,'batch-0002',f,previous=cp,previous_sha='0'*64)
   self.assertEqual(len(f.calls),before)
   with c.Lease(root):
    with self.assertRaises((OSError,ValueError)):self.batch(root,'batch-0002',f,previous=cp,previous_sha=c.sha(cp))
   with self.assertRaises(InterruptedError):self.batch(root,'batch-0002',f,previous=cp,previous_sha=c.sha(cp),cancel=lambda:True)
   self.assertEqual(json.loads((root/'session-state.json').read_text())['state'],'BLOCKED')
 def test_full_synthetic_30days_and_no_false_ready(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);f=Fake();prev=None;pin=None
   for n in range(1,12):
    receipt=self.batch(root,f'batch-{n:04}',f,previous=prev,previous_sha=pin);prev=root/f'batch-{n:04}/checkpoint.json';pin=c.sha(prev)
    if receipt['status']=='READY':break
   self.assertEqual(receipt['status'],'READY');self.assertEqual(n,9);self.assertEqual(receipt['session_requests'],177)
   self.assertEqual(sum(x['count'] for t in receipt['coverage'].values() for x in t.values()),155520)
   receipt['status']='PARTIAL';cp=root/'forged.json';cp.write_bytes(c.canonical(receipt))
   with self.assertRaises((ValueError,FileNotFoundError)):v.verify_checkpoint(cp,c.sha(cp))
 def test_oracle_rejects_wrong_eligibility_and_counters(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);f=Fake();cpdata=self.batch(root,'batch-0001',f);cp=root/'batch-0001/forged.json'
   for override in [dict(eligible=[]),dict(batch_requests=1)]:
    cp.write_bytes(c.canonical(dict(cpdata,**override)))
    with self.assertRaises(ValueError):v.verify_checkpoint(cp,c.sha(cp))
 def test_cancel_during_final_empty_page_blocks(self):
  class Empty(Fake):
   cancelled=False
   def __call__(self,path,p):
    body,meta=super().__call__(path,p);data=json.loads(body)
    if path.endswith('/instruments-info'):data['result']['list']=[data['result']['list'][-1]]
    if path.endswith('/kline'):
     data['result']['list']=[]
     if p['interval']=='5':self.cancelled=True
    body=json.dumps(data).encode();meta.update(body_sha256=hashlib.sha256(body).hexdigest(),body_bytes=len(body));return body,meta
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);f=Empty()
   with self.assertRaises(InterruptedError):self.batch(root,'batch-0001',f,cancel=lambda:f.cancelled)
   self.assertEqual(json.loads((root/'session-state.json').read_text())['state'],'BLOCKED')
 def test_backdated_first_observation_rejected(self):
  import sqlite3
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);f=Fake();receipt=self.batch(root,'batch-0001',f);dbpath=root/'batch-0001/history.sqlite3';db=sqlite3.connect(dbpath)
   for id,raw in list(db.execute('select id,meta from sources')):
    meta=json.loads(raw);meta['observed_start_utc']=meta['observed_end_utc']='1970-01-01T00:00:00+00:00';db.execute('update sources set meta=? where id=?',(json.dumps(meta),id))
   db.commit();db.close();receipt['database_sha256']=c.sha(dbpath);cp=root/'batch-0001/forged.json';cp.write_bytes(c.canonical(receipt))
   with self.assertRaises(ValueError):v.verify_checkpoint(cp,c.sha(cp))
if __name__=='__main__':unittest.main()
