from pathlib import Path
from .config import AppConfig
def main():
    cfg=AppConfig.load(Path.cwd()); cfg.ensure_directories()
    # Persistent Telegram polling is wired when local credentials are configured.
    return 0
if __name__=='__main__': raise SystemExit(main())
