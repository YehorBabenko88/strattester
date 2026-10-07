from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from enum import Enum
from zoneinfo import ZoneInfo


class Availability(str, Enum):
    AVAILABLE = "AVAILABLE"
    DRAINING = "DRAINING"
    SCHEDULED_OFFLINE = "SCHEDULED_OFFLINE"


@dataclass(frozen=True)
class WorkSchedule:
    timezone_name: str = "Europe/Berlin"
    start: time = time(15, 0)
    stop: time = time(5, 0)
    sunday_24h: bool = True

    def localize(self, now: datetime | None = None) -> datetime:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return now.astimezone(ZoneInfo(self.timezone_name))

    def allows_new_work(self, now: datetime | None = None) -> bool:
        local = self.localize(now)
        if self.sunday_24h and local.weekday() == 6:
            return True
        t = local.timetz().replace(tzinfo=None)
        return t >= self.start or t < self.stop

    def state(self, now: datetime | None = None, *, active_jobs: int = 0) -> Availability:
        if self.allows_new_work(now):
            return Availability.AVAILABLE
        if active_jobs > 0:
            return Availability.DRAINING
        return Availability.SCHEDULED_OFFLINE


UNRESTRICTED = None


def schedule_for_node(node_id: str | None) -> WorkSchedule | None:
    # PC1 is intentionally constrained by the physical-host operating window.
    if (node_id or "").strip().upper() == "PC1":
        return WorkSchedule()
    return UNRESTRICTED


def can_accept_new_work(node_id: str | None, now: datetime | None = None) -> bool:
    schedule = schedule_for_node(node_id)
    return True if schedule is None else schedule.allows_new_work(now)
