from datetime import datetime, timezone
from strattester.runtime.work_schedule import Availability, WorkSchedule, can_accept_new_work

def utc(y,m,d,h,minute=0):
    return datetime(y,m,d,h,minute,tzinfo=timezone.utc)

def test_pc1_boundaries_winter_berlin():
    # 2026-12-07 Monday; Berlin is UTC+1.
    s=WorkSchedule()
    assert s.allows_new_work(utc(2026,12,7,3,59))       # 04:59
    assert not s.allows_new_work(utc(2026,12,7,4,0))    # 05:00
    assert not s.allows_new_work(utc(2026,12,7,13,59))  # 14:59
    assert s.allows_new_work(utc(2026,12,7,14,0))       # 15:00

def test_sunday_is_full_day():
    s=WorkSchedule()
    assert s.allows_new_work(utc(2026,12,6,5,0))
    assert s.allows_new_work(utc(2026,12,6,13,0))
    assert s.allows_new_work(utc(2026,12,6,22,59))

def test_saturday_to_sunday_and_sunday_to_monday():
    s=WorkSchedule()
    assert s.allows_new_work(utc(2026,12,5,23,0))
    assert s.allows_new_work(utc(2026,12,6,23,0)) # Monday 00:00 local
    assert s.allows_new_work(utc(2026,12,7,3,59))
    assert not s.allows_new_work(utc(2026,12,7,4,0))

def test_dst_uses_europe_berlin_local_clock():
    s=WorkSchedule()
    # 2026-07-06 Monday; Berlin is UTC+2.
    assert s.allows_new_work(utc(2026,7,6,2,59))        # 04:59
    assert not s.allows_new_work(utc(2026,7,6,3,0))    # 05:00
    assert not s.allows_new_work(utc(2026,7,6,12,59))  # 14:59
    assert s.allows_new_work(utc(2026,7,6,13,0))       # 15:00

def test_draining_does_not_hard_kill_active_work():
    s=WorkSchedule()
    blocked=utc(2026,12,7,10,0)
    assert s.state(blocked,active_jobs=1) == Availability.DRAINING
    assert s.state(blocked,active_jobs=0) == Availability.SCHEDULED_OFFLINE

def test_other_nodes_are_unrestricted():
    blocked=utc(2026,12,7,10,0)
    assert not can_accept_new_work("PC1",blocked)
    assert can_accept_new_work("LS5",blocked)
    assert can_accept_new_work("PC2",blocked)
