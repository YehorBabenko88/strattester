"""Hosted installed-consumer check; never imports retired source packages."""
import importlib.metadata as metadata
import importlib.util
import os
import json
from pathlib import Path
import tempfile

class StrictFrozenRoster:
    """Require the complete reviewed roster to pass setup, call and teardown."""
    def __init__(self, expected):
        if len(expected)!=14 or len(set(expected))!=14:
            raise ValueError('exact fourteen-case roster required')
        self.expected=tuple(expected);self.errors=[];self.reports={};self.collected=False;self.accepted=False

    def pytest_collection_finish(self,session):
        actual=[item.nodeid for item in session.items]
        self.collected=True
        if sorted(actual)!=sorted(self.expected):self.errors.append('unexpected or incomplete collection roster')

    def pytest_deselected(self,items):
        if items:self.errors.append('deselected obligations')

    def pytest_collectreport(self,report):
        if report.outcome!='passed':self.errors.append('collection did not pass')

    def pytest_runtest_logreport(self,report):
        key=(report.nodeid,report.when)
        if report.nodeid not in self.expected or report.when not in ('setup','call','teardown'):
            self.errors.append('unexpected execution report')
        if key in self.reports:self.errors.append('duplicate execution report')
        self.reports[key]=report.outcome
        if report.outcome!='passed' or hasattr(report,'wasxfail'):
            self.errors.append('skipped, failed, xfail or xpass obligation')

    def pytest_sessionfinish(self,session,exitstatus):
        required={(node,phase) for node in self.expected for phase in ('setup','call','teardown')}
        self.accepted=(exitstatus==0 and self.collected and not self.errors
                       and set(self.reports)==required
                       and all(value=='passed' for value in self.reports.values()))
        if not self.accepted:session.exitstatus=1

    def pytest_terminal_summary(self,terminalreporter):
        if not self.accepted:
            terminalreporter.write_sep('=', 'STRICT FROZEN CONSUMER REFUSED: '+('; '.join(self.errors) or 'missing successful execution reports'))


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
            expected=json.loads((source/"scripts/frozen_consumer_roster.json").read_text(encoding="utf-8"))
            guard=StrictFrozenRoster(expected)
            result=pytest.main(["--confcutdir",str(source/"integration_tests"),str(source/"integration_tests/test_frozen_results.py"),"-q"],plugins=[guard])
            return 0 if int(result)==0 and guard.accepted else 1
        finally:
            os.chdir(previous)

if __name__ == "__main__":
    raise SystemExit(main())
