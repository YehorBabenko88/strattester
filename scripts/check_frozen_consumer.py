"""Hosted installed-consumer check; never imports retired source packages."""
import importlib.metadata as metadata
import importlib.util
import os
from pathlib import Path
import tempfile

def main():
    source = Path(__file__).resolve().parents[1]
    previous = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="canonical-frozen-consumer-") as temporary:
        os.chdir(temporary)
        try:
            import market_math
            import terminan.research_archive as archive
            import terminan.migration.research_results as migration
            for module, distribution in ((market_math,"unified-math-kernels"),(archive,"unified-terminan"),(migration,"unified-terminan")):
                origin = Path(module.__file__).resolve()
                installed = Path(metadata.distribution(distribution).locate_file("")).resolve()
                if not origin.is_relative_to(installed) or origin.is_relative_to(source):
                    raise AssertionError("consumer module did not originate from installed distribution")
            for name in ("grid","strattester","meta_analyse","market_profile_math"):
                if importlib.util.find_spec(name) is not None:
                    raise AssertionError("retired package fallback is visible: " + name)
            import pytest
            return pytest.main(["--confcutdir",str(source/"integration_tests"),str(source/"integration_tests/test_frozen_results.py"),"-q"])
        finally:
            os.chdir(previous)

if __name__ == "__main__":
    raise SystemExit(main())
