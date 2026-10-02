from pathlib import Path
from strattester.config import AppConfig


def test_defaults_use_local_directories(tmp_path: Path):
    cfg = AppConfig.load(tmp_path)
    assert cfg.data_dir == tmp_path / 'data'
    assert cfg.results_dir == tmp_path / 'results'
    assert cfg.logs_dir == tmp_path / 'logs'
    assert cfg.state_dir == tmp_path / 'state'


def test_repr_redacts_telegram_token(tmp_path: Path, monkeypatch):
    monkeypatch.setenv('STRATTESTER_TELEGRAM_TOKEN', 'super-secret-token')
    cfg = AppConfig.load(tmp_path)
    assert 'super-secret-token' not in repr(cfg)
