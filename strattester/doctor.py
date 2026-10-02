from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import sys
import tempfile

from .config import AppConfig


@dataclass(frozen=True)
class DoctorReport:
    python_supported: bool
    paths_writable: bool
    market_db_exists: bool
    free_disk_bytes: int
    postgres_configured: bool
    tailscale_available: bool


def _paths_writable(config: AppConfig) -> bool:
    try:
        config.ensure_directories()
        for directory in (config.data_dir, config.results_dir, config.logs_dir, config.state_dir):
            with tempfile.NamedTemporaryFile(dir=directory, delete=True):
                pass
        return True
    except OSError:
        return False


def run_doctor(config: AppConfig) -> DoctorReport:
    return DoctorReport(
        python_supported=sys.version_info >= (3, 11),
        paths_writable=_paths_writable(config),
        market_db_exists=config.market_db.is_file(),
        free_disk_bytes=shutil.disk_usage(config.root).free,
        postgres_configured=bool(os.getenv('STRATTESTER_POSTGRES_DSN')),
        tailscale_available=shutil.which('tailscale') is not None,
    )
