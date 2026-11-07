"""Separate actual JSONSchema target; not part of stdlib-only unit suite."""
import argparse,copy,json,pathlib,sys
import jsonschema
from support import ROOT,sha,canonical

def unique(pairs):
 out={}
 for key,value in pairs:
  if key in out:raise ValueError('duplicate artifact JSON key')
  out[key]=value
 return out

def validate(folder):
 folder=pathlib.Path(folder);schemas=ROOT/'docs/gateway/research';checks=0;validators={};values={};raws={}
 for name,file in [('request','request.schema.json'),('meta-result','meta-result.schema.json'),('descriptor','result.schema.json')]:
  schema=json.loads((schemas/file).read_bytes());jsonschema.Draft202012Validator.check_schema(schema)
  validator=jsonschema.Draft202012Validator(schema);validators[name]=validator
  raw=(folder/(name+'.json')).read_bytes();raws[name]=raw;value=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite')));values[name]=value
  assert raw==canonical(value),'canonical bytes changed';validator.validate(value);checks+=1
  for field in value:
   bad=copy.deepcopy(value);del bad[field];assert list(validator.iter_errors(bad)),(name,field);checks+=1
 d=values['descriptor'];assert d['artifact']['raw_sha256']==sha(raws['meta-result']) and d['artifact']['byte_count']==str(len(raws['meta-result']));checks+=1
 assert d['request_raw_sha256']==sha(raws['request']);checks+=1
 for key in ['state','scope','production_runtime_admission']:
  bad=copy.deepcopy(d);bad[key]='PASS';assert list(validators['descriptor'].iter_errors(bad));checks+=1
 for value in [None,0,'0','1.00']:
  bad=copy.deepcopy(d);bad['financial']['fees']=value
  if value is None:validators['descriptor'].validate(bad)
  else:assert list(validators['descriptor'].iter_errors(bad))
  checks+=1
 for bad_value in ['NaN','Infinity','12\n','<script>','0'*65]:
  bad=copy.deepcopy(values['meta-result']);bad['levels'][0]['price']=bad_value;assert list(validators['meta-result'].iter_errors(bad));checks+=1
 bad=copy.deepcopy(values['meta-result']);bad['levels']*=129;assert list(validators['meta-result'].iter_errors(bad));checks+=1
 bad=copy.deepcopy(values['request']);bad['payload']['rows']*=86;assert list(validators['request'].iter_errors(bad));checks+=1
 for field in ['request_raw_sha256']:
  bad=copy.deepcopy(d);bad[field]+='\n';assert list(validators['descriptor'].iter_errors(bad));checks+=1
 for field in d['clocks']:
  bad=copy.deepcopy(d);bad['clocks'][field]+='\n';assert list(validators['descriptor'].iter_errors(bad));checks+=1
 for value,good in [('9223372036854775807',True),('9223372036854775808',False),('01',False),('1\n',False)]:
  bad=copy.deepcopy(values['request']);bad['experiment']['revision']=value
  assert (not list(validators['request'].iter_errors(bad)))==good;checks+=1
 return {'schema_checks':checks,'skips':0,'qualification':'LOCAL_SCHEMA_COMPONENT_ONLY','jsonschema_version':__import__('importlib.metadata',fromlist=['version']).version('jsonschema'),'schema_sha256':{p.name:sha(p.read_bytes()) for p in schemas.glob('*.schema.json')}}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--artifacts',required=True);a=parser.parse_args();print(json.dumps(validate(a.artifacts)))
