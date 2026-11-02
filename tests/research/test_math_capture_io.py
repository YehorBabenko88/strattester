"""A child-owned output cursor must not be queried during resource polling."""
import hashlib
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from strattester.research.grid_math_history import MathClient


class MathCaptureTests(unittest.TestCase):
    def test_real_worker_capture_never_queries_shared_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'history_worker.py'
            source.write_text("import json,time\ntime.sleep(.03)\nprint(json.dumps({'value':'x'*32000}))\n")
            client=MathClient(root,'fixture','fixture','fixture',output_limit=65536)
            client.temp=True;client.path=root;client.started=time.monotonic()
            client.manifest={'history_worker.py':hashlib.sha256(source.read_bytes()).hexdigest()}
            real_file=tempfile.TemporaryFile
            class ChildFile:
                def __init__(self,*args,**kwargs):self.file=real_file(*args,**kwargs)
                def __enter__(self):return self
                def __exit__(self,*args):return self.file.__exit__(*args)
                def __getattr__(self,name):return getattr(self.file,name)
                def tell(self):raise AssertionError('shared child cursor queried')
            with patch('strattester.research.grid_math_history.tempfile.TemporaryFile',ChildFile):
                self.assertEqual(client._execute({}),{'value':'x'*32000})


if __name__=='__main__':unittest.main()
