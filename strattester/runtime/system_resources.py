import os,shutil
import psutil
from strattester.engine.resource_manager import ResourceSnapshot

def snapshot(path):
    vm=psutil.virtual_memory(); disk=shutil.disk_usage(path)
    return ResourceSnapshot(
        vm.total,vm.available,disk.free,
        psutil.cpu_percent(interval=None),
        psutil.cpu_count(logical=True) or os.cpu_count() or 1)
