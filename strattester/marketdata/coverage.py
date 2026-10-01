from dataclasses import dataclass

@dataclass(frozen=True)
class TimeRange:
    start: int
    end: int

@dataclass(frozen=True)
class Coverage:
    earliest: int | None
    latest: int | None
    count: int
    gaps: tuple[TimeRange, ...] = ()
