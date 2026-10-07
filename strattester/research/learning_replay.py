"""Replay learning events strictly after the checkpoint boundary."""
from __future__ import annotations
from dataclasses import dataclass
import copy
from .decision_memory import ObservedOutcome
from .learning_event_log import LearningEvent

@dataclass(frozen=True)
class ReplayReport:
    start_sequence:int
    end_sequence:int
    applied:int
    skipped:int

class LearningReplayEngine:
    def replay(self,org,events):
        start=int(org.last_applied_learning_sequence);applied=0;skipped=0
        ordered=sorted(events,key=lambda e:e.sequence)
        # Preflight the complete batch before the first adaptive mutation.
        future=[e for e in ordered if e.sequence>start]
        seen=start
        for e in future:
            if e.sequence<=seen:raise ValueError("non-monotonic learning sequence")
            if e.decision_id not in org.decision_memory.traces:
                raise ValueError(f"missing decision trace for replay: {e.decision_id}")
            seen=e.sequence
        seen=start
        for e in ordered:
            if e.sequence<=org.last_applied_learning_sequence:
                skipped+=1;continue
            if e.sequence<=seen:raise ValueError("non-monotonic learning sequence")
            if e.decision_id not in org.decision_memory.traces:
                raise ValueError(f"missing decision trace for replay: {e.decision_id}")
            outcome=ObservedOutcome(e.decision_id,e.horizon,e.utility,e.timestamp_ms)
            org.learn_decision(outcome,dict(e.attribution),regime=e.regime,
                               counterfactuals=e.counterfactuals)
            org.last_applied_learning_sequence=e.sequence
            seen=e.sequence;applied+=1
        return ReplayReport(start,org.last_applied_learning_sequence,applied,skipped)
