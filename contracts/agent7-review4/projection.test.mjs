import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {projectResearch,projectPaper,canonicalize,decodeScientific} from './project.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex');
const uid='12345678-1234-4123-8123-123456789abc';
const context=()=>({
 cluster_id:uid,recovery_generation:uid,registry_dataset_id:uid,registry_revision:'1',
 source_id:uid,partition_id:uid,job_id:uid,assignment_id:uid,lease_id:uid,lease_epoch:'1',
 worker_id:uid,worker_incarnation:uid,account_id:null,ledger_id:null,
 implementation_commit:'a'.repeat(40),implementation_tree:'b'.repeat(40),
 implementation_manifest_sha256:'c'.repeat(64),storage_manifest_sha256:'d'.repeat(64),artifact_id:uid
});
const clocks=['decision_ms','snapshot_as_of_ms','window_start_ms','window_end_ms','data_available_at_ms','calculated_at_ms'];
function research(){return {schema:'meta.ohlcv.research.result.v1',mode:'HISTORICAL_RESEARCH',
 dataset_id:'e'.repeat(64),request_digest:'f'.repeat(64),units:{price:'USDT/BTC',volume:'BTC'},
 rows:[{event_start_ms:0,event_end_ms:60000,open:1,high:1,low:1,close:1,volume:0.1}],
 ...Object.fromEntries(clocks.map(k=>[k,60000])),source_authenticity:'NOT_EVALUATED',
 execution_authority:false,trading_authorized:false,training_authorized:false,h_b_eligible:false};}
function paper(){return {schema:'stratt.paper.quote.snapshot.v1',mode:'PUBLIC_QUOTE_PAPER_RESEARCH',
 source_authenticity:'NOT_EVALUATED',receipt_provenance:'CALLER_DECLARED',
 durability:'NODE_LOCAL_NOT_DISTRIBUTED_CONSENSUS_OR_FAILOVER',execution_authority:false,
 trading_authorized:false,ledger_scope:'CHECKPOINTED_ROLLBACK_JOURNAL_ONLY',live_wal_supported:false,
 missing_state:['OPEN_POSITIONS','ACCOUNT_EQUITY','BALANCE','UNREALIZED_PNL'],
 selection_order:['admitted_ms DESC','request_id DESC'],validated_count:1,returned_count:1,has_more:false,
 rows:[{result:{pnl:0.10000000000000002}}]};}
const encode=x=>Buffer.from(JSON.stringify(x));
const select=()=>({row_index:'0',field:'volume',unit_key:'volume'});
function runResearch(x=research(),c=context(),s=select()){const b=Buffer.isBuffer(x)?x:encode(x);return projectResearch(b,hash(b),c,s);}
function runPaper(x=paper(),c={...context(),account_id:uid,ledger_id:uid}){const b=Buffer.isBuffer(x)?x:encode(x);return projectPaper(b,hash(b),c);}
test('research keeps full raw artifact identity and explicitly partial scalar encoding',()=>{
 const raw=Buffer.from(JSON.stringify(research(),null,2));
 const out=runResearch(raw);
 assert.equal(out.artifact.raw_sha256,hash(raw));assert.equal(out.artifact.byte_count,String(raw.length));
 assert.equal(out.scalar.bits_be_hex,'3fb999999999999a');assert.equal(out.scalar.unit,'BTC');
 assert.equal(out.row_count,'1');assert.equal(out.projection_complete,false);
 assert.equal(out.lineage.registry_dataset_id,uid);assert.equal(out.legacy_dataset_digest,'e'.repeat(64));
 for(const k of clocks)assert.equal(out.clocks[k],'60000');
 assert.equal(out.execution_authority,false);assert.equal(out.trading_authorized,false);
 assert.equal(decodeScientific(out.scalar.bits_be_hex),0.1);
 assert.deepEqual(JSON.parse(canonicalize(out)),out);
});
test('negative zero source bit pattern survives JSON token decoding',()=>{
 const raw=encode(research()).toString().replace('"volume":0.1','"volume":-0');
 const out=runResearch(Buffer.from(raw));assert.equal(out.scalar.bits_be_hex,'8000000000000000');
 assert.ok(Object.is(decodeScientific(out.scalar.bits_be_hex),-0));
});
test('paper references entire bounded source selection without copying rounded money',()=>{
 const out=runPaper();assert.equal(out.returned_count,'1');assert.equal(out.validated_count,'1');
 assert.equal(out.has_more,false);assert.equal(out.selection_scope,'BOUNDED_SOURCE_SELECTION_NOT_FULL_HISTORY');
 assert.equal(out.financial_values,'UNAVAILABLE_A3_A4_UNIT_DECIMAL_PROFILE_PENDING');
 assert.ok(!('rows' in out));assert.equal(out.missing_state.length,4);
 assert.equal(out.lineage.account_id,uid);assert.equal(out.source_authenticity,'NOT_EVALUATED');
});
test('research 2000 rows stays one explicit reference, not inline split or truncated history',()=>{
 const x=research();x.rows=Array.from({length:2000},()=>x.rows[0]);
 const out=runResearch(x);assert.equal(out.row_count,'2000');assert.ok(!('rows' in out));
});
test('paper full 200 row selection references all bytes and reports further history',()=>{
 const x=paper();x.rows=Array.from({length:200},()=>x.rows[0]);x.returned_count=200;x.validated_count=201;x.has_more=true;
 const out=runPaper(x);assert.equal(out.returned_count,'200');assert.equal(out.has_more,true);
 assert.equal(out.artifact.raw_sha256,hash(encode(x)));
});
test('raw digest mismatch is rejected',()=>assert.throws(()=>projectResearch(encode(research()),'0'.repeat(64),context(),select()),/DIGEST/));
for(const [name,mutate] of [
 ['boolean clock',x=>x.decision_ms=true],['string clock',x=>x.decision_ms='60000'],
 ['unsafe clock',x=>x.decision_ms=9007199254740992],['authority enabled',x=>x.execution_authority=true],
 ['wrong schema',x=>x.schema='meta.ohlcv.research.result.v0'],
 ['wrong source authenticity',x=>x.source_authenticity='VERIFIED'],
 ['missing dataset digest',x=>delete x.dataset_id],['too many research rows',x=>x.rows=Array(2001).fill(x.rows[0])],
 ['string scalar',x=>x.rows[0].volume='0.1'],['boolean scalar',x=>x.rows[0].volume=false],
 ['unit mismatch',x=>x.units.volume=''],['training enabled',x=>x.training_authorized=true]
])test('rejects research '+name,()=>{const x=research();mutate(x);assert.throws(()=>runResearch(x));});
for(const [name,raw] of [
 ['duplicate decoded keys','{"schema":"x","sch\u0065ma":"y"}'],
 ['unsafe integer token',encode(research()).toString().replace('"volume":0.1','"volume":9007199254740993')],
 ['noncanonical integer clock',encode(research()).toString().replace('"decision_ms":60000','"decision_ms":6e4')],
 ['nonfinite scalar',encode(research()).toString().replace('"volume":0.1','"volume":1e999')],
 ['trailing source content',encode(research()).toString()+' true']
])test('rejects '+name,()=>assert.throws(()=>runResearch(Buffer.from(raw))));
for(const [name,mutate] of [
 ['row count mismatch',x=>x.returned_count=0],['has-more mismatch',x=>x.has_more=true],
 ['too many paper rows',x=>{x.rows=Array(201).fill(x.rows[0]);x.returned_count=201;x.validated_count=201;}],
 ['unknown missing state',x=>x.missing_state.push('MADE_UP')],['live WAL',x=>x.live_wal_supported=true],
 ['wrong durability',x=>x.durability='DISTRIBUTED'],['quorum claim',x=>x.execution_authority=true]
])test('rejects paper '+name,()=>{const x=paper();mutate(x);assert.throws(()=>runPaper(x));});
for(const [name,mutate] of [
 ['numeric epoch',c=>c.lease_epoch=1],['epoch overflow',c=>c.lease_epoch='9223372036854775808'],
 ['leading zero revision',c=>c.registry_revision='01'],['unknown lineage field',c=>c.live=true],
 ['bad dataset UUID',c=>c.registry_dataset_id='e'.repeat(64)],
 ['bad implementation pin',c=>c.implementation_commit='A'.repeat(40)],
 ['missing storage manifest',c=>delete c.storage_manifest_sha256]
])test('rejects lineage '+name,()=>{const c=context();mutate(c);assert.throws(()=>runResearch(research(),c));});
test('paper requires declared account and ledger lineage',()=>assert.throws(()=>runPaper(paper(),context())));
test('research refuses paper account lineage',()=>assert.throws(()=>runResearch(research(),{...context(),account_id:uid})));
test('selection is explicit and refuses out-of-range or finance field invention',()=>{
 for(const s of [{...select(),row_index:'1'},{...select(),field:'pnl'},{...select(),unit_key:'price'}])
 assert.throws(()=>runResearch(research(),context(),s));
});
test('getter lineage is refused without executing it',()=>{
 const c=context();let called=false;Object.defineProperty(c,'lease_epoch',{enumerable:true,get(){called=true;return '1';}});
 assert.throws(()=>runResearch(research(),c));assert.equal(called,false);
});
test('proxy lineage is refused without executing traps',()=>{
 let called=false;const c=new Proxy(context(),{ownKeys(){called=true;throw Error('trap');}});
 assert.throws(()=>runResearch(research(),c));assert.equal(called,false);
});
test('C3 has canonical ASCII ordering and only quote/backslash escapes',()=>{
 assert.equal(canonicalize({z:true,a:'a"b\\c'}),'{"a":"a\\"b\\\\c","z":true}');
});
for(const [name,x] of [
 ['numeric literal',{a:1}],['unicode',{a:'é'}],['array over resource cap',{a:Array(33).fill(null)}],
 ['sparse array',{a:Array(1)}],['big string',{a:'x'.repeat(16385)}],['deep nesting',Array.from({length:13}).reduce(x=>({a:x}),null)],
 ['hidden key',Object.defineProperty({},'x',{value:'hidden'})],['symbol key',{[Symbol('x')]:'a'}]
])test('C3 refuses '+name,()=>assert.throws(()=>canonicalize(x)));
test('C3 refuses nonordinary arrays and enumerable extra keys',()=>{
 const x=[];x.extra=true;assert.throws(()=>canonicalize(x));
 const y=[];Object.setPrototypeOf(y,null);assert.throws(()=>canonicalize(y));
});
test('frozen ordinary objects and dense arrays remain valid',()=>assert.equal(canonicalize(Object.freeze({a:Object.freeze(['x'])})),'{"a":["x"]}'));
for(const bits of ['7ff0000000000000','fff0000000000000','7ff8000000000001','FFFFFFFFFFFFFFFF','0'])
 test('decode refuses nonfinite/malformed '+bits,()=>assert.throws(()=>decodeScientific(bits)));

test('C3 rejects control characters including final newline and DEL',()=>{
 for(const x of ['x\n','x\r','x\t','\x7f','\x00'])assert.throws(()=>canonicalize({a:x}));
 assert.throws(()=>canonicalize({'x\n':'y'}));
});
test('lineage UUID and bit strings reject trailing newlines',()=>{
 assert.throws(()=>runResearch(research(),{...context(),worker_id:uid+'\n'}));
 assert.throws(()=>decodeScientific('3fb999999999999a\n'));
});

const {readFile}=await import('node:fs/promises');
const vectors=JSON.parse(await readFile(new URL('./vectors.json',import.meta.url),'utf8'));
for(const vector of vectors.positive)test('published producer vector '+vector.name,()=>{
 const raw=Buffer.from(vector.raw_source_utf8),copy=Buffer.from(raw);
 const out=vector.operation==='projectResearch'
  ?projectResearch(raw,vector.expected_raw_sha256,vector.context,vector.selection)
  :projectPaper(raw,vector.expected_raw_sha256,vector.context);
 assert.deepEqual(out,vector.expected_value);assert.equal(canonicalize(out),vector.expected_c3);
 assert.equal(hash(canonicalize(out)),vector.expected_c3_sha256);assert.deepEqual(raw,copy);
});
for(const vector of vectors.negative)test('published negative vector '+vector.name,()=>{
 const fn={decodeScientific,canonicalize}[vector.operation];assert.throws(()=>fn(vector.value));
});

test('source container depth exactly 64 accepted and 65 rejected',()=>{
 const good=research();good.extra=Array.from({length:63}).reduce(x=>[x],null);
 assert.equal(runResearch(good).row_count,'1');
 const bad=research();bad.extra=Array.from({length:63}).reduce(x=>[x],[]);
 assert.throws(()=>runResearch(bad),/SOURCE_LIMIT/);
});

test('package manifest binds exact raw bytes without self-hash cycle',async()=>{
 const manifest=JSON.parse(await readFile(new URL('./MANIFEST.json',import.meta.url),'utf8'));
 assert.equal(manifest.status,'PROPOSED_DOMAIN_SCHEMA_ACK_PENDING');
 assert.equal(manifest.files.length,8);
 for(const entry of manifest.files){
  assert.notEqual(entry.path,'MANIFEST.json');
  const bytes=await readFile(new URL('./'+entry.path,import.meta.url));
  assert.equal(hash(bytes),entry.sha256);assert.equal(String(bytes.length),entry.byte_count);
 }
 for(const name of ['research-reference.schema.json','paper-reference.schema.json','numeric-profile.json','vectors.json','MANIFEST.json']){
  const bytes=await readFile(new URL('./'+name,import.meta.url));
  assert.ok(bytes.every(x=>x>=32&&x<=126));assert.notEqual(bytes.at(-1),10);
 }
});
