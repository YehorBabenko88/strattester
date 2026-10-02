from pathlib import Path
from strattester.deploy.updater import UpdateManager
from strattester.deploy.releases import UpdateCandidate
def make_source(p):
    p.mkdir(); (p/'app.py').write_text('ok'); (p/'data').mkdir(); (p/'data'/'db').write_text('never copy')
def test_stage_excludes_runtime_data(tmp_path):
    src=tmp_path/'src'; make_source(src)
    u=UpdateManager(tmp_path/'root',lambda p:True)
    s=u.stage(UpdateCandidate('abcdef123456',src))
    assert (s.path/'app.py').exists() and not (s.path/'data').exists()
def test_failed_healthcheck_rolls_back(tmp_path):
    root=tmp_path/'root'; root.mkdir(); old=root/'releases'/'old'; old.mkdir(parents=True)
    (root/'current.txt').write_text(str(old))
    src=tmp_path/'src'; make_source(src)
    u=UpdateManager(root,lambda p:False); s=u.stage(UpdateCandidate('abcdef123456',src))
    r=u.activate(s)
    assert not r.ok and r.rolled_back
    assert Path((root/'current.txt').read_text())==old
