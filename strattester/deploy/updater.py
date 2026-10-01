from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os,shutil
from .releases import UpdateCandidate,StagedRelease
@dataclass(frozen=True)
class ActivationResult:
    ok:bool
    active:Path|None
    rolled_back:bool=False
class UpdateManager:
    def __init__(self,root:Path,healthcheck):
        self.root=Path(root); self.releases=self.root/'releases'; self.current=self.root/'current'; self.healthcheck=healthcheck
    def stage(self,candidate:UpdateCandidate):
        if len(candidate.commit_sha)<7 or not candidate.source.is_dir(): raise ValueError('invalid immutable update candidate')
        dst=self.releases/candidate.commit_sha
        if dst.exists(): shutil.rmtree(dst)
        self.releases.mkdir(parents=True,exist_ok=True)
        shutil.copytree(candidate.source,dst,ignore=shutil.ignore_patterns('data','state','results','logs','.git'))
        return StagedRelease(candidate.commit_sha,dst)
    def _read_current(self):
        marker=self.root/'current.txt'
        return Path(marker.read_text(encoding='utf-8').strip()) if marker.exists() else None
    def _write_current(self,path:Path):
        tmp=self.root/'current.txt.tmp'; marker=self.root/'current.txt'
        tmp.write_text(str(path),encoding='utf-8'); os.replace(tmp,marker)
    def activate(self,staged:StagedRelease):
        previous=self._read_current()
        self._write_current(staged.path)
        result=self.healthcheck(staged.path)
        if not result:
            if previous:self._write_current(previous)
            return ActivationResult(False,previous,True)
        return ActivationResult(True,staged.path,False)
    def rollback(self):
        # explicit rollback requires caller to retain/select a known-good release
        raise RuntimeError('explicit target required; automatic rollback occurs during activation')
