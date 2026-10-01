from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True)
class UpdateCandidate:
    commit_sha:str
    source:Path
@dataclass(frozen=True)
class StagedRelease:
    commit_sha:str
    path:Path
