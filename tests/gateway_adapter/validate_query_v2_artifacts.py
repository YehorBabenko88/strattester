"""Optional actual JSON Schema/URI registry checks; no runtime admission."""
import argparse,copy,json,pathlib
from jsonschema import Draft202012Validator
from referencing import Registry,Resource
ROOT=pathlib.Path(__file__).resolve().parents[2]
def validate(directory):
 directory=pathlib.Path(directory);schemas=ROOT/'docs/gateway/research';registry=Registry();checks=[];loaded={}
 for name in ('request.schema.json','result.schema.json','query-v2-request.schema.json','query-v2-result.schema.json'):
  schema=json.loads((schemas/name).read_bytes());Draft202012Validator.check_schema(schema)
  registry=registry.with_resource(schema['$id'],Resource.from_contents(schema));loaded[name]=schema
 assert len(list(registry))==4,'v1/v2 URI collision'
 checks.append('four-versioned-resources-coexist')
 for schema_name,file_name in (('query-v2-request.schema.json','request.json'),('query-v2-result.schema.json','descriptor.json')):
  schema=loaded[schema_name];value=json.loads((directory/file_name).read_bytes())
  # Resolve through the actual URI registry, not just direct local schema dicts.
  validator=Draft202012Validator({'$ref':schema['$id']},registry=registry)
  validator.validate(value);checks.append(file_name+':valid')
  for key in schema['required']:
   changed=copy.deepcopy(value);del changed[key]
   assert list(validator.iter_errors(changed));checks.append(file_name+':missing:'+key)
  changed=copy.deepcopy(value);changed['unexpected']=True
  assert list(validator.iter_errors(changed));checks.append(file_name+':closed')
  changed=copy.deepcopy(value);changed['schema']='stratt.gateway.synthetic.research.'+('request' if file_name=='request.json' else 'result')+'.v1-review1'
  assert list(validator.iter_errors(changed));checks.append(file_name+':v1-refused')
 meta_schema=json.loads((schemas/'meta-result.schema.json').read_bytes());Draft202012Validator(meta_schema).validate(json.loads((directory/'meta-result.json').read_bytes()));checks.append('actual-meta-artifact-valid')
 print(json.dumps({'checks':len(checks),'names':checks,'skips':0,'qualification':'STRUCTURAL_SCHEMA_AND_URI_REGISTRY_ONLY'},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--artifacts',required=True);validate(p.parse_args().artifacts)
