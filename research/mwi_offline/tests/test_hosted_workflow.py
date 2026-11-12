import json
from pathlib import Path
import unittest

class Checks(unittest.TestCase):
    def test_contained_suite_has_pinned_read_only_hosted_lane(self):
        root=Path(__file__).resolve().parents[3]
        w=json.loads((root/'.github/workflows/mwi-offline-research.yml').read_text())
        self.assertEqual(set(w),{'name','on','permissions','jobs'})
        self.assertEqual(w['permissions'],{'contents':'read'})
        self.assertEqual(set(w['on']),{'push','pull_request'})
        for event in w['on'].values():
            self.assertEqual(event['paths'],['research/mwi_offline/**','docs/research/MWI_OFFLINE.md','.github/workflows/mwi-offline-research.yml'])
        self.assertEqual(set(w['jobs']),{'offline'})
        job=w['jobs']['offline'];self.assertEqual(job['timeout-minutes'],10)
        self.assertEqual(set(job),{'runs-on','timeout-minutes','strategy','steps'})
        self.assertEqual(job['strategy'],{'fail-fast':False,'matrix':{'os':['ubuntu-latest','windows-latest']}})
        self.assertEqual(job['runs-on'],'${{ matrix.os }}')
        self.assertEqual(job['steps'],[
            {'uses':'actions/checkout@11d5960a326750d5838078e36cf38b85af677262','env':{'GIT_CONFIG_COUNT':'2','GIT_CONFIG_KEY_0':'core.autocrlf','GIT_CONFIG_VALUE_0':'false','GIT_CONFIG_KEY_1':'core.eol','GIT_CONFIG_VALUE_1':'lf'},'with':{'ref':'${{ github.event.pull_request.head.sha || github.sha }}','persist-credentials':False}},
            {'uses':'actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065','with':{'python-version':'3.12'}},
            {'name':'Run contained offline tests','run':'python -I -S -B research/mwi_offline/run_tests.py'}])

if __name__=='__main__':unittest.main(verbosity=2)
