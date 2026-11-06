"""Isolated raw Git source preconditions; not a financial/native PASS witness."""
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest

SOURCE = Path(__file__).resolve().parents[2]
FILES = ('scripts/financial_gate.py', 'scripts/financial-gate-manifest.json',
         'strattester/__init__.py', 'strattester/research/__init__.py',
         'strattester/research/financial_acceptance.py',
         'strattester/research/financial_contract.py')


def fixture(tmp_path, monkeypatch, namespace, kind):
    # Prevent inherited Git path/config overrides from reaching any primary repo.
    for key in list(os.environ):
        if key.startswith('GIT_'):
            monkeypatch.delenv(key)
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', os.devnull)
    env = dict(os.environ)
    seed, root = tmp_path / 'seed', tmp_path / 'clone'
    seed.mkdir()
    def git(at, *args, raw=True, data=None):
        command = ['git'] + (['--no-replace-objects'] if raw else [])
        return subprocess.check_output(command + ['-c', 'core.hooksPath=' + os.devnull,
            '-c', 'core.autocrlf=false', '-C', str(at), *args], input=data,
            env=env, stderr=subprocess.PIPE, timeout=15).strip()
    git(seed, 'init', '-q')
    for name in FILES:
        target = seed / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((SOURCE / name).read_bytes())
    (seed / '.gitignore').write_bytes(b'__pycache__/\n')
    (seed / 'inert.txt').write_bytes(b'canonical fixture bytes\n')
    git(seed, 'add', '.')
    git(seed, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-qm', 'isolated source fixture')
    git(seed, 'clone', '--no-hardlinks', str(seed), str(root))
    assert (root / '.git').is_dir()
    assert not (root / '.git/objects/info/alternates').exists()
    head = git(root, 'rev-parse', 'HEAD').decode()
    tree = git(root, 'rev-parse', 'HEAD^{tree}').decode()
    original = replacement = None
    if kind == 'blob':
        original = git(root, 'rev-parse', 'HEAD:inert.txt').decode()
        replacement = git(root, 'hash-object', '-w', '--stdin', data=b'virtual inert bytes\n').decode()
    elif kind in ('tree', 'commit'):
        replacement = git(root, 'mktree', data=b'').decode()
        original = tree
        if kind == 'commit':
            original = head
            replacement = git(root, '-c', 'user.name=Fixture', '-c',
                'user.email=fixture@example.invalid', 'commit-tree', replacement,
                '-p', head, data=b'virtual commit\n').decode()
    if original:
        git(root, 'update-ref', namespace + '/' + original, replacement)
    env['GIT_REPLACE_REF_BASE'] = namespace + '/'
    if original:
        assert git(root, 'cat-file', kind, original, raw=False) == git(root, 'cat-file', kind, replacement)
        assert git(root, 'cat-file', kind, original, raw=False) != git(root, 'cat-file', kind, original)
    assert git(root, 'rev-parse', 'HEAD').decode() == head
    assert git(root, 'rev-parse', 'HEAD^{tree}').decode() == tree
    assert git(root, 'status', '--porcelain') == b''
    return SimpleNamespace(root=root, env=env, head=head, git=git)


def probe(f, tmp_path):
    # Invalid gate stops before torch/tests/aggregation; reaching this exact error
    # establishes source preconditions only and must never be called acceptance.
    return subprocess.run([sys.executable, '-B', 'scripts/financial_gate.py',
        '--gate', '__agent7_readonly_source_probe__', '--sha', f.head,
        '--output', str(tmp_path / 'output')], cwd=f.root, env=f.env,
        capture_output=True, text=True, timeout=20)


@pytest.mark.parametrize('namespace', ['refs/replace', 'refs/agent7-replacements'])
@pytest.mark.parametrize('kind', ['clean', 'blob', 'tree', 'commit'])
def test_raw_clean_checkout_ignores_virtual_objects(tmp_path, monkeypatch, namespace, kind):
    f = fixture(tmp_path, monkeypatch, namespace, kind)
    result = probe(f, tmp_path)
    assert result.returncode != 0  # Intentional unknown-gate refusal, never PASS.
    assert 'unknown gate' in result.stderr
    assert 'uncommitted tracked changes' not in result.stderr


@pytest.mark.parametrize('namespace', ['refs/replace', 'refs/agent7-replacements'])
def test_raw_gate_still_rejects_real_tracked_change(tmp_path, monkeypatch, namespace):
    f = fixture(tmp_path, monkeypatch, namespace, 'commit')
    (f.root / 'inert.txt').write_bytes(b'actual dirty checkout\n')
    assert f.git(f.root, 'status', '--porcelain')
    result = probe(f, tmp_path)
    assert result.returncode != 0
    assert 'uncommitted tracked changes' in result.stderr
    assert 'unknown gate' not in result.stderr
