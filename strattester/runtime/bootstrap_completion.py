"""Finalize historical bootstrap only when all durable research jobs are terminal."""
from __future__ import annotations
from pathlib import Path
from strattester.engine.jobs import JobState
from .phase_manifest import PhaseManifest
from .grid_handoff import write_handoff
from strattester.research.scientific_bootstrap import export_scientific_bootstrap

ACTIVE={JobState.PENDING,JobState.BLOCKED,JobState.READY,JobState.LEASED,
        JobState.RUNNING,JobState.CHECKPOINTED,JobState.RETRYABLE}

class BootstrapCompletionCoordinator:
    def __init__(self,state_store,market_store,root:Path):
        self.state_store=state_store;self.market_store=market_store;self.root=Path(root)
        self.phase=PhaseManifest(self.root/"state"/"phase-manifest.json")
    def status(self):
        jobs=list(self.state_store.list_jobs())
        states={}
        for j in jobs:states[j.state.value]=states.get(j.state.value,0)+1
        active=sum(1 for j in jobs if j.state in ACTIVE)
        failed=sum(1 for j in jobs if j.state is JobState.FAILED)
        return {"jobs":len(jobs),"active":active,"failed":failed,"states":states,
                "ready_to_finalize":bool(jobs) and active==0 and failed==0}
    def finalize_if_ready(self,symbols):
        st=self.status()
        if not st["ready_to_finalize"]:return {"finalized":False,**st}
        phase=self.phase.load()
        if phase.get("phase") in ("GRID_IMPORT","LIVE_LEARNING","PAPER_TRADING"):
            return {"finalized":True,"already":True,**st}
        self.phase.advance("HISTORICAL_SCIENCE_BOOTSTRAP",{"jobs":st})
        science=self.root/"results"/"historical-science-bootstrap.json"
        bundle=export_scientific_bootstrap(self.market_store,symbols,science)
        handoff=self.root/"results"/"grid-handoff.json"
        write_handoff(handoff,science,
                      strategy_results_path=self.root/"results"/"research_results.sqlite3",
                      phase_manifest_path=self.root/"state"/"phase-manifest.json")
        self.phase.advance("GRID_IMPORT",{"science_bundle":str(science),"handoff":str(handoff)})
        return {"finalized":True,"science_bundle":str(science),"handoff":str(handoff),
                "symbols":len(bundle.get("symbols") or ()),**st}
