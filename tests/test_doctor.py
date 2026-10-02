from pathlib import Path
from strattester.config import AppConfig
from strattester.doctor import run_doctor


def test_doctor_does_not_create_missing_market_db(tmp_path: Path):
    cfg = AppConfig.load(tmp_path)
    report = run_doctor(cfg)
    assert not cfg.market_db.exists()
    assert report.market_db_exists is False
    assert report.paths_writable is True
