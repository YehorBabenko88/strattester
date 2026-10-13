"""Read-only diagnostic entry point for physical node commissioning."""
from pathlib import Path
import json
from dataclasses import asdict

from .config import AppConfig
from .doctor import run_doctor


def main():
    report = run_doctor(AppConfig.load(Path.cwd()))
    print(json.dumps(asdict(report), sort_keys=True))
    return 0 if report.python_supported and report.paths_writable else 2


if __name__ == "__main__":
    raise SystemExit(main())
