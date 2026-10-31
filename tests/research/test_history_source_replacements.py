"""Git replacement refs cannot replace executable bytes below a pinned tree."""
from pathlib import Path
import subprocess

import pytest


def git(root, *args, input=None):
    return subprocess.check_output(['git', '-C', str(root), *args], input=input).strip()


@pytest.mark.parametrize('namespace', ['refs/replace', 'refs/alternate-replacements'])
def test_pinned_worker_extraction_ignores_blob_replacement(tmp_path, monkeypatch, namespace):
    from strattester.research.grid_math_history import FILES, MathClient, runtime_pin
    monkeypatch.delenv('GIT_NO_REPLACE_OBJECTS', raising=False)
    root = tmp_path / 'source'
    root.mkdir()
    git(root, 'init', '-q')
    original = b'print("ORIGINAL_PINNED_WORKER")\n'
    replacement = b'print("UNTRUSTED_REPLACEMENT_WORKER")\n'
    for name in FILES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(original)
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'pinned source')
    commit = git(root, '--no-replace-objects', 'rev-parse', 'HEAD').decode()
    tree = git(root, '--no-replace-objects', 'rev-parse', 'HEAD^{tree}').decode()
    blob = git(root, '--no-replace-objects', 'rev-parse', 'HEAD:python/history_worker.py').decode()
    substitute = git(root, 'hash-object', '-w', '--stdin', input=replacement).decode()
    git(root, 'update-ref', namespace + '/' + blob, substitute)
    # Replacement iteration trims the namespace prefix; current Git requires
    # this prefix to end in '/', otherwise it aborts before object lookup.
    monkeypatch.setenv('GIT_REPLACE_REF_BASE', namespace + '/')
    # Trusted metadata must refer to raw source objects, independently of the
    # poisoned namespace. Ordinary post-poison peeling aborts in some Git builds
    # before the consumer is exercised; it is not the attack witness below.
    assert git(root, '--no-replace-objects', 'rev-parse', 'HEAD').decode() == commit
    assert git(root, '--no-replace-objects', 'rev-parse', 'HEAD^{tree}').decode() == tree
    assert git(root, '--no-replace-objects', 'status', '--porcelain') == b''
    # Keep replacement-aware Git active here and inside an unhardened consumer.
    # Direct blob lookup avoids native Git commit/tree peeling regressions while
    # still proving the actual replacement-aware object lookup returns poison.
    assert git(root, 'cat-file', 'blob', blob) == replacement.strip()
    with MathClient(root, commit, tree, runtime_pin()) as client:
        assert (client.path / 'history_worker.py').read_bytes() == original
