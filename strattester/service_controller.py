from pathlib import Path
from .config import AppConfig
from .runtime.control_status import ControlStatus
from .runtime.logging import build_logger
from .runtime.service_manager import WindowsServiceManager
from .telegram.commands import ConfirmationStore
from .telegram.controller import TelegramController
from .telegram.poller import TelegramPoller

def main():
    cfg=AppConfig.load(Path.cwd()); cfg.ensure_directories()
    log=build_logger(cfg.logs_dir/'controller.jsonl','strattester.controller')
    if not cfg.telegram_token or not cfg.telegram_chat_id:
        log.error('telegram credentials missing; controller not started')
        return 2
    inspection=ControlStatus(cfg.root)
    controller=TelegramController(
        [cfg.telegram_chat_id],WindowsServiceManager(root=cfg.root),
        lambda: str(inspection.status()),ConfirmationStore(),inspection=inspection)
    log.info('controller started')
    TelegramPoller(cfg.telegram_token,controller).run()
    return 0
if __name__=='__main__': raise SystemExit(main())
