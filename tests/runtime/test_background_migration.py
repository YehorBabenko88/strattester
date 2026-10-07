from strattester.runtime.background_migration import BackgroundShardMigration
from strattester.engine.resource_manager import ResourceSnapshot

GB=1024**3
class Migrator:
    def __init__(self): self.calls=[]
    def migrate_batch(self,symbols,**kw):
        self.calls.append((list(symbols),kw)); return 'ok'

def test_background_migration_runs_only_with_normal_resource_headroom():
    m=Migrator()
    snap=lambda:ResourceSnapshot(16*GB,12*GB,100*GB,20,8)
    bg=BackgroundShardMigration(m,lambda:['BTCUSDT'],snap,5*GB,batch_symbols=2,interval_seconds=60)
    assert bg.maybe_run(now=100)=='ok'
    assert len(m.calls)==1
    assert bg.maybe_run(now=120) is None
    assert len(m.calls)==1
    assert bg.maybe_run(now=161)=='ok'
    assert len(m.calls)==2

def test_background_migration_pauses_under_cpu_ram_or_disk_pressure():
    for snap in (
        ResourceSnapshot(16*GB,12*GB,100*GB,95,8),
        ResourceSnapshot(16*GB,1*GB,100*GB,10,8),
        ResourceSnapshot(16*GB,12*GB,1*GB,10,8),
    ):
        m=Migrator()
        bg=BackgroundShardMigration(m,lambda:['BTCUSDT'],lambda s=snap:s,5*GB)
        assert bg.maybe_run(now=100) is None
        assert m.calls==[]
