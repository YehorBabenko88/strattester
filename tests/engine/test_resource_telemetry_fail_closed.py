from strattester.engine.resource_manager import ResourceSnapshot, decide_resources


def test_invalid_cpu_telemetry_blocks_heavy_jobs():
    snapshot = ResourceSnapshot(64 * 1024**3, 48 * 1024**3, 100 * 1024**3, float('nan'), 8)
    decision = decide_resources(snapshot)
    assert decision.allow_heavy is False
    assert decision.max_new_jobs == 0


def test_invalid_ram_telemetry_blocks_heavy_jobs():
    snapshot = ResourceSnapshot(64 * 1024**3, float('nan'), 100 * 1024**3, 20, 8)
    decision = decide_resources(snapshot)
    assert decision.allow_heavy is False
    assert decision.max_new_jobs == 0
