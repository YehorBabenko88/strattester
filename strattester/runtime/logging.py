from __future__ import annotations
import json,logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
class JsonFormatter(logging.Formatter):
    def format(self,record):
        d={'timestamp':self.formatTime(record),'level':record.levelname,'component':getattr(record,'component','runtime'),'event':record.getMessage()}
        for k in ('job_id','symbol','strategy_id','strategy_version'):
            v=getattr(record,k,None)
            if v is not None:d[k]=v
        return json.dumps(d,ensure_ascii=False)
def build_logger(path:Path,name='strattester',max_bytes=10_000_000,backup_count=5):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    l=logging.getLogger(name); l.setLevel(logging.INFO); l.handlers.clear()
    h=RotatingFileHandler(path,maxBytes=max_bytes,backupCount=backup_count,encoding='utf-8'); h.setFormatter(JsonFormatter()); l.addHandler(h)
    return l
