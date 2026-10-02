from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os


@dataclass(frozen=True)
class AppConfig:
    root: Path
    data_dir: Path
    results_dir: Path
    logs_dir: Path
    state_dir: Path
    market_db: Path
    telegram_token: str | None = field(default=None, repr=False)
    telegram_chat_id: str | None = None

    @classmethod
    def load(cls, root: Path) -> 'AppConfig':
        root = Path(root).expanduser().resolve()
        data_dir = root / 'data'
        return cls(
            root=root,
            data_dir=data_dir,
            results_dir=root / 'results',
            logs_dir=root / 'logs',
            state_dir=root / 'state',
            market_db=data_dir / 'bybit_1m.sqlite3',
            telegram_token=os.getenv('STRATTESTER_TELEGRAM_TOKEN'),
            telegram_chat_id=os.getenv('STRATTESTER_TELEGRAM_CHAT_ID'),
        )

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.results_dir, self.logs_dir, self.state_dir):
            path.mkdir(parents=True, exist_ok=True)
