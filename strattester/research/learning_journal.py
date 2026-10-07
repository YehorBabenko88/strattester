"""Crash-safe learning journal protocol.

A durable store may claim an event before mutation, then mark it APPLIED after
successful learning. CLAIMED events are recoverable and never silently treated as
completed learning.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class LearningJournalState:
    event_id:str
    decision_id:str
    horizon:str
    status:str

class LearningJournal:
    def __init__(self,store):self.store=store

    def begin(self,event_id,decision_id,horizon,*,meta=None):
        if hasattr(self.store,"begin_learning_event"):
            return self.store.begin_learning_event(event_id,decision_id,horizon,meta=meta)
        return self.store.claim_learning_event(event_id,decision_id,horizon,meta=meta)

    def commit(self,event_id):
        if hasattr(self.store,"complete_learning_event"):
            return self.store.complete_learning_event(event_id)
        return True

    def status(self,event_id):
        if hasattr(self.store,"learning_event_status"):
            return self.store.learning_event_status(event_id)
        return None

    def recoverable(self):
        if hasattr(self.store,"pending_learning_events"):
            return tuple(self.store.pending_learning_events())
        return ()
