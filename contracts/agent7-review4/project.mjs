// Offline contract projection only. No admission, storage, trading or research engine.
import {createHash} from 'node:crypto';
import {types} from 'node:util';
const need=(ok,code='INVALID_PROJECTION')=>{if(!ok)throw new TypeError(code);};
const hex64=/^[0-9a-f]{64}$/;
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const ascii=s=>typeof s==='string'&&/^[\x20-\x7e]*$/.test(s);
const u63=s=>typeof s==='string'&&/^(0|[1-9][0-9]{0,18})$/.test(s)&&BigInt(s)<=9223372036854775807n;
const clocks=['decision_ms','snapshot_as_of_ms','window_start_ms','window_end_ms','data_available_at_ms','calculated_at_ms'];
const missing=['OPEN_POSITIONS','ACCOUNT_EQUITY','BALANCE','UNREALIZED_PNL'];
const order=['admitted_ms DESC','request_id DESC'];
const hash=b=>createHash('sha256').update(b).digest('hex');
function own(o,array=false){
 need(o!==null&&typeof o==='object'&&!types.isProxy(o),'HOST_SHAPE');
 need(Object.getPrototypeOf(o)===(array?Array.prototype:Object.prototype),'HOST_SHAPE');
 const d=Object.getOwnPropertyDescriptors(o);
 for(const k of Reflect.ownKeys(d)){
  need(typeof k==='string','HOST_SHAPE');
  if(array&&k==='length')continue;
  need(d[k].enumerable&&Object.hasOwn(d[k],'value'),'HOST_SHAPE');
 }
 return d;
}
function closed(o,keys){
 own(o);need(Object.keys(o).sort().join('|')===[...keys].sort().join('|'),'CLOSED_FIELDS');
}
export function canonicalize(value){
 let nodes=0;
 function visit(x,depth){
  need(++nodes<=32768,'C3_NODES');
  if(x===null||typeof x==='boolean')return JSON.stringify(x);
  if(typeof x==='string'){need(ascii(x)&&x.length<=16384,'C3_STRING');return JSON.stringify(x);}
  need(x!==null&&typeof x==='object','C3_TYPE');need(depth+1<=12,'C3_DEPTH');
  const array=Array.isArray(x),d=own(x,array);
  if(array){
   need(x.length<=32&&Object.keys(d).length===x.length+1,'C3_ARRAY');
   const parts=[];for(let i=0;i<x.length;i++){need(Object.hasOwn(d,String(i)),'C3_ARRAY');parts.push(visit(d[i].value,depth+1));}
   return '['+parts.join(',')+']';
  }
  const keys=Object.keys(d).sort();need(keys.length<=64,'C3_MEMBERS');
  return '{'+keys.map(k=>{
   need(ascii(k)&&k.length>=1&&k.length<=128,'C3_KEY');need(++nodes<=32768,'C3_NODES');
   return JSON.stringify(k)+':'+visit(d[k].value,depth+1);
  }).join(',')+'}';
 }
 const out=visit(value,0);need(out.length<=2097152,'C3_BYTES');return out;
}
// Parse JSON number lexemes without globally coercing integers or financial data.
// Tags are parser-private; duplicate decoded object keys are rejected.
class Numeric {constructor(text){this.text=text;}}
function parseSource(raw,maxBytes,expected){
 need(Buffer.isBuffer(raw)&&raw.length>0&&raw.length<=maxBytes,'SOURCE_BYTES');
 need(typeof expected==='string'&&hex64.test(expected)&&hash(raw)===expected,'SOURCE_DIGEST');
 const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(raw);
 need(text.charCodeAt(0)!==0xfeff,'SOURCE_BOM');
 let i=0,nodes=0;
 const white=()=>{while(i<text.length&&/[ \t\r\n]/.test(text[i]))i++;};
 function string(){
  const start=i++;let escaped=false;
  while(i<text.length){
   const c=text[i++];if(!escaped&&c==='"'){
    const s=JSON.parse(text.slice(start,i));need(s.length<=65536,'SOURCE_STRING');return s;
   }
   if(!escaped&&c==='\\')escaped=true;else escaped=false;
  }
  throw new TypeError('SOURCE_JSON');
 }
 function value(depth=0){
  need(++nodes<=250000,'SOURCE_LIMIT');white();const c=text[i];
  if(c==='"')return string();
  if(c==='{'||c==='['){
   need(depth<64,'SOURCE_LIMIT');
   const object=c==='{',out=object?{}:[];i++;white();
   const end=object?'}':']';if(text[i]===end){i++;return out;}
   while(true){
    if(object){
     need(text[i]==='"','SOURCE_JSON');const k=string();white();need(text[i++]===':','SOURCE_JSON');
     need(!Object.hasOwn(out,k),'SOURCE_DUPLICATE_KEY');
     Object.defineProperty(out,k,{value:value(depth+1),enumerable:true,writable:true,configurable:true});
    }else{need(out.length<8192,'SOURCE_ARRAY');out.push(value(depth+1));}
    white();if(text[i]===end){i++;return out;}
    need(text[i++ ]===',','SOURCE_JSON');white();
   }
  }
  for(const [literal,x] of [['true',true],['false',false],['null',null]]){
   if(text.startsWith(literal,i)){i+=literal.length;return x;}
  }
  const m=/-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(text.slice(i));
  need(m&&m.index===0,'SOURCE_JSON');i+=m[0].length;return new Numeric(m[0]);
 }
 const out=value();white();need(i===text.length,'SOURCE_TRAILING');need(out&&typeof out==='object'&&!Array.isArray(out),'SOURCE_OBJECT');return out;
}
function integer(x,max=9007199254740991n){
 need(x instanceof Numeric&&/^(0|[1-9][0-9]*)$/.test(x.text),'SOURCE_INTEGER');
 const n=BigInt(x.text);need(n<=max,'SOURCE_INTEGER_RANGE');return x.text;
}
function scalar(x){
 need(x instanceof Numeric,'SOURCE_SCALAR');
 // Integer tokens must be exactly representable before explicit binary64 decode.
 if(/^-?[0-9]+$/.test(x.text))need(BigInt(x.text)>=-9007199254740991n&&BigInt(x.text)<=9007199254740991n,'UNSAFE_INTEGER_SCALAR');
 const n=Number(x.text);need(Number.isFinite(n),'NONFINITE_SCALAR');
 const b=Buffer.alloc(8);b.writeDoubleBE(n);return b.toString('hex');
}
export function decodeScientific(bits){
 need(typeof bits==='string'&&/^[0-9a-f]{16}$/.test(bits),'SCALAR_BITS');
 const n=Buffer.from(bits,'hex').readDoubleBE();need(Number.isFinite(n),'NONFINITE_SCALAR');return n;
}
const ids=['cluster_id','recovery_generation','registry_dataset_id','source_id','partition_id','job_id','assignment_id','lease_id','worker_id','worker_incarnation','artifact_id'];
const extra=['registry_revision','lease_epoch','account_id','ledger_id','implementation_commit','implementation_tree','implementation_manifest_sha256','storage_manifest_sha256'];
function lineage(c,paper){
 closed(c,[...ids,...extra]);
 for(const k of ids)need(typeof c[k]==='string'&&uuid.test(c[k]),'LINEAGE_UUID');
 for(const k of ['registry_revision','lease_epoch'])need(u63(c[k]),'LINEAGE_U63');
 for(const k of ['implementation_commit','implementation_tree'])need(typeof c[k]==='string'&&/^[0-9a-f]{40}$/.test(c[k]),'IMPLEMENTATION_PIN');
 for(const k of ['implementation_manifest_sha256','storage_manifest_sha256'])need(typeof c[k]==='string'&&hex64.test(c[k]),'MANIFEST_PIN');
 for(const k of ['account_id','ledger_id'])need(paper?typeof c[k]==='string'&&uuid.test(c[k]):c[k]===null,'ACCOUNT_LINEAGE');
 const out={};for(const k of [...ids,...extra])if(!['artifact_id','storage_manifest_sha256'].includes(k))out[k]=c[k];
 return out;
}
function base(raw,digest,c,isPaper,schema){
 return {
  schema,lineage:lineage(c,isPaper),
  artifact:{artifact_id:c.artifact_id,storage_manifest_sha256:c.storage_manifest_sha256,raw_sha256:digest,
   byte_count:String(raw.length),source_schema:isPaper?'stratt.paper.quote.snapshot.v1':'meta.ohlcv.research.result.v1',
   retrieval_status:'REQUIRES_ADMITTED_STORAGE_AND_INDEPENDENT_HASH_VERIFICATION'},
  source_authenticity:'NOT_EVALUATED',lineage_status:'CALLER_DECLARED_NOT_AUTHORITY_ACK',
  execution_authority:false,trading_authorized:false,training_authorized:false,
  acceptance:'OFFLINE_CONTRACT_MODEL_ONLY',projection_complete:false
 };
}
function disabled(x){need(x.source_authenticity==='NOT_EVALUATED'&&x.execution_authority===false&&x.trading_authorized===false,'SOURCE_CAPABILITY');}
export function projectResearch(raw,expected,c,selection){
 const x=parseSource(raw,16777216,expected);disabled(x);
 need(x.schema==='meta.ohlcv.research.result.v1'&&x.mode==='HISTORICAL_RESEARCH'&&x.training_authorized===false&&x.h_b_eligible===false,'SOURCE_SCHEMA');
 need(typeof x.dataset_id==='string'&&hex64.test(x.dataset_id)&&typeof x.request_digest==='string'&&hex64.test(x.request_digest),'LEGACY_DIGEST');
 need(Array.isArray(x.rows)&&x.rows.length>=1&&x.rows.length<=2000,'RESEARCH_ROWS');
 closed(selection,['row_index','field','unit_key']);
 need(u63(selection.row_index)&&BigInt(selection.row_index)<BigInt(x.rows.length),'ROW_INDEX');
 need(['open','high','low','close','volume'].includes(selection.field),'SCIENTIFIC_FIELD');
 const unitKey=selection.field==='volume'?'volume':'price';need(selection.unit_key===unitKey,'SCIENTIFIC_UNIT');
 need(x.units&&ascii(x.units[unitKey])&&x.units[unitKey].length>0&&x.units[unitKey].length<=128,'SCIENTIFIC_UNIT');
 const out=base(raw,expected,c,false,'agent7.research.reference.review4.v1');
 out.legacy_dataset_digest=x.dataset_id;out.legacy_request_digest=x.request_digest;
 out.row_count=String(x.rows.length);out.clocks={};
 for(const k of clocks)out.clocks[k]=integer(x[k]);
 out.clock_unit='UTC_UNIX_MILLISECONDS';out.analysis_clock='CALCULATED_NOW_NOT_HISTORICAL_OBSERVATION';
 out.scalar={row_index:selection.row_index,field:selection.field,unit_key:unitKey,unit:x.units[unitKey],
  bits_be_hex:scalar(x.rows[Number(selection.row_index)]?.[selection.field]),
  source_encoding:'JSON_NUMBER_DECODED_IEEE754_BINARY64',scale:'IEEE754_BINARY64_NO_DECIMAL_RESCALE',
  purpose:'SCIENTIFIC_OBSERVATION_NOT_FINANCIAL_EXECUTION'};
 canonicalize(out);return out;
}
export function projectPaper(raw,expected,c){
 const x=parseSource(raw,1048576,expected);disabled(x);
 need(x.schema==='stratt.paper.quote.snapshot.v1'&&x.mode==='PUBLIC_QUOTE_PAPER_RESEARCH','SOURCE_SCHEMA');
 need(x.receipt_provenance==='CALLER_DECLARED'&&x.durability==='NODE_LOCAL_NOT_DISTRIBUTED_CONSENSUS_OR_FAILOVER'&&
 x.ledger_scope==='CHECKPOINTED_ROLLBACK_JOURNAL_ONLY'&&x.live_wal_supported===false,'PAPER_SCOPE');
 need(JSON.stringify(x.missing_state)===JSON.stringify(missing)&&JSON.stringify(x.selection_order)===JSON.stringify(order),'PAPER_SELECTION');
 const returned=integer(x.returned_count,200n),validated=integer(x.validated_count,1024n);
 need(Array.isArray(x.rows)&&x.rows.length===Number(returned)&&BigInt(validated)>=BigInt(returned)&&
 typeof x.has_more==='boolean'&&x.has_more===(BigInt(validated)>BigInt(returned)),'PAPER_COUNTS');
 const out=base(raw,expected,c,true,'agent7.paper.reference.review4.v1');
 Object.assign(out,{returned_count:returned,validated_count:validated,has_more:x.has_more,
  selection_scope:'BOUNDED_SOURCE_SELECTION_NOT_FULL_HISTORY',selection_order:[...order],missing_state:[...missing],
  financial_values:'UNAVAILABLE_A3_A4_UNIT_DECIMAL_PROFILE_PENDING',
  durability:x.durability,ledger_scope:x.ledger_scope,live_wal_supported:false,receipt_provenance:x.receipt_provenance});
 canonicalize(out);return out;
}
