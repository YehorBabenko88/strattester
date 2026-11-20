"""Report-level adversarial controls for both actual reviewed test rosters."""
import json,runpy,types
from pathlib import Path
root=Path(__file__).resolve().parent
Guard=runpy.run_path(str(root/'canonical_test_gate.py'))['StrictTestRoster']

def check(expected,count):
 def control(change):
  g=Guard(expected,expected_count=count);s=types.SimpleNamespace(items=[types.SimpleNamespace(nodeid=x) for x in expected],exitstatus=0)
  g.pytest_collection_finish(s)
  for node in expected:
   for phase in ('setup','call','teardown'):g.pytest_runtest_logreport(types.SimpleNamespace(nodeid=node,when=phase,outcome='passed'))
  change(g,s);g.pytest_sessionfinish(s,0);return g.accepted,s.exitstatus
 assert control(lambda g,s:None)==(True,0)
 changes={
 'skipped':lambda g,s:g.pytest_runtest_logreport(types.SimpleNamespace(nodeid=expected[0],when='call',outcome='skipped')),
 'xfail':lambda g,s:g.pytest_runtest_logreport(types.SimpleNamespace(nodeid=expected[0],when='call',outcome='skipped',wasxfail='expected')),
 'xpass':lambda g,s:g.pytest_runtest_logreport(types.SimpleNamespace(nodeid=expected[0],when='call',outcome='passed',wasxfail='expected')),
 'missing_phase':lambda g,s:g.reports.pop((expected[0],'teardown')),
 'deselected':lambda g,s:g.pytest_deselected([s.items[0]]),
 'collection_error':lambda g,s:g.pytest_collectreport(types.SimpleNamespace(outcome='failed')),
 'collection_skip':lambda g,s:g.pytest_collectreport(types.SimpleNamespace(outcome='skipped')),
 'unexpected_roster':lambda g,s:g.pytest_collection_finish(types.SimpleNamespace(items=s.items+[types.SimpleNamespace(nodeid='unexpected')])),
 'incomplete_roster':lambda g,s:g.pytest_collection_finish(types.SimpleNamespace(items=s.items[:-1])),
 'duplicate_report':lambda g,s:g.pytest_runtest_logreport(types.SimpleNamespace(nodeid=expected[0],when='call',outcome='passed')),
 'empty_reports':lambda g,s:g.reports.clear(),
 }
 for name,change in changes.items():assert control(change)==(False,1),name
 for nodes,expected_count in ((expected,True),(expected,count-1),(expected+[expected[0]],count+1)):
  try:Guard(nodes,expected_count=expected_count)
  except ValueError:pass
  else:raise AssertionError('invalid roster constructor accepted')
 return {'cases':count,'positive':1,'negative_reports':list(changes),'negative_constructors':3}

results=[check(json.loads((root/name).read_text()),count) for name,count in (('frozen_consumer_roster.json',14),('canonical_test_roster.json',772))]
print(json.dumps({'all_passed':True,'results':results}))
