import threading
class Lifecycle:
    def __init__(self): self._stop=threading.Event(); self._drain=threading.Event()
    def request_stop(self): self._stop.set()
    def request_drain(self): self._drain.set()
    @property
    def stopping(self): return self._stop.is_set()
    @property
    def draining(self): return self._drain.is_set()
