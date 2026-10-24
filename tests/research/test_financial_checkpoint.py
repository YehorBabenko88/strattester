import json
import os
from hashlib import sha256
import subprocess
import sys
import pytest
import torch
from strattester.research.financial_structural_model import StructuralConfig, build_structural_model
from strattester.research.financial_checkpoint import save_checkpoint, load_checkpoint


def test_checkpoint_reloads_in_fresh_process_and_refuses_replay(tmp_path):
    torch.manual_seed(8);model=build_structural_model(StructuralConfig(recycles=0))
    path=tmp_path/'model.json'; digest=save_checkpoint(model,path,dataset_sha256='a'*64,seed=8)
    loaded,metadata=load_checkpoint(path,digest)
    x=torch.ones(1,2,3,3);m=torch.ones(1,2,3,dtype=torch.bool)
    torch.testing.assert_close(model(x,m),loaded(x,m),rtol=0,atol=0)
    code="from strattester.research.financial_checkpoint import load_checkpoint; import torch,json,sys; m,_=load_checkpoint(sys.argv[1],sys.argv[2]); print(json.dumps(m(torch.ones(1,2,3,3),torch.ones(1,2,3,dtype=torch.bool)).detach().tolist()))"
    result=subprocess.run([sys.executable,'-c',code,str(path),digest],capture_output=True,text=True,check=True,timeout=60)
    assert json.loads(result.stdout)==model(x,m).detach().tolist()
    assert metadata['dataset_sha256']=='a'*64
    with pytest.raises(ValueError,match='exists'):save_checkpoint(model,path,dataset_sha256='a'*64,seed=8)


@pytest.mark.parametrize('kind',['tamper','shape','nan','oversize','config','duplicate'])
def test_checkpoint_rejects_untrusted_shapes_and_serialization(tmp_path,kind):
    model=build_structural_model(StructuralConfig());path=tmp_path/'model.json'
    digest=save_checkpoint(model,path,dataset_sha256='a'*64,seed=0)
    p=json.loads(path.read_text());name=next(iter(p['tensors']))
    if kind=='tamper':path.write_text('{}')
    elif kind=='shape':p['tensors'][name]['shape']=[99999]
    elif kind=='nan':p['tensors'][name]['values'][0]=float('nan')
    elif kind=='config':p['config']['hidden']=10**9
    elif kind=='duplicate':path.write_text('{"version":1,"version":1}')
    if kind not in ('tamper','duplicate','oversize'):
        path.write_text(json.dumps(p));digest=sha256(path.read_bytes()).hexdigest()
    if kind=='duplicate':digest=sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):load_checkpoint(path,digest,max_bytes=10 if kind=='oversize' else 8*1024*1024)


def test_installed_evaluation_does_not_depend_on_repository_working_directory(tmp_path):
    code="from strattester.research.financial_evaluation import evaluate_controls; r=evaluate_controls([[0.],[1.]],[0.,.1],[[2.]],[.2],train_events=[('BTC',0),('BTC',1)],test_events=[('BTC',2)]); assert len(r)==7"
    result=subprocess.run([sys.executable,'-I','-c',code],cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
