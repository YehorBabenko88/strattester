import json
import pytest
from strattester.data_first_cli import main

def test_connection_plan_is_readonly_and_not_authorization(tmp_path,capsys,monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(['plan-connection'])==0
    report=json.loads(capsys.readouterr().out)
    assert report['LS5_CONNECTED_SYNC']=='NOT_AUTHORIZED'
    assert report['credentials'].startswith('NONE')
    assert not list(tmp_path.iterdir())

def test_connected_cli_requires_explicit_flag_before_files_or_network(tmp_path):
    target=tmp_path/'new'
    with pytest.raises(SystemExit) as caught:
        main(['run','--root',str(target),'--start-ms','0','--end-ms','60000'])
    assert caught.value.code==2 and not target.exists()

def test_existing_unowned_root_rejected_before_clients(tmp_path):
    with pytest.raises(SystemExit) as caught:
        main(['run','--root',str(tmp_path),'--start-ms','0','--end-ms','60000','--allow-network'])
    assert caught.value.code==2 and not list(tmp_path.iterdir())
