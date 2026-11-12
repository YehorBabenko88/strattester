import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mwi_offline.strategy import candidates
from mwi_offline.learning_lab import build_learning_lab_preview,DOMAINS

class Checks(unittest.TestCase):
    def setUp(self):self.cs=candidates('a'*64,'b'*64)[:2]
    def test_nine_proposal_domains_no_adopted_endpoint(self):
        r=build_learning_lab_preview(self.cs,'c'*64)
        self.assertEqual(len(DOMAINS),9);self.assertEqual(set(r['domains']),set(DOMAINS))
        self.assertEqual(r['evidence_class'],'SYNTHETIC')
        self.assertEqual(r['publication_status'],'LOCAL_UNATTESTED')
        self.assertEqual(r['adoption_status'],'PROPOSED_NOT_ADOPTED')
        self.assertEqual(r['owner_field_ack'],'PENDING')
        self.assertEqual(r['source_context'],'UNKNOWN')
        for key in ('endpoint','owner_experiment_id','owner_job_id'):self.assertIsNone(r[key])
        for key in ('live','submitted','authenticated','execution_authority','training_authorized','trading_authorized'):
            self.assertIs(r[key],False)
        self.assertEqual(r['terminan_source_context']['commit'],'2a8e2647700dad4f661057235e13f76dc52f091f')
    def test_unknown_values_never_fabricated_from_candidate_presence(self):
        r=build_learning_lab_preview(self.cs,'c'*64)
        for name,d in r['domains'].items():
            self.assertEqual(d['status'],'PROPOSED_NOT_ADOPTED')
            if name!='strategy_candidates':self.assertIsNone(d['data'])
        self.assertEqual(r['domains']['strategy_candidates']['data'][0]['state'],'LOCAL_RESEARCH_CANDIDATE_ONLY')
    def test_boundaries_duplicates_mixed_datasets_and_hashes(self):
        for cs,pin in (([], 'c'*64),(self.cs*4,'c'*64),([self.cs[0],self.cs[0]],'c'*64),(self.cs,'bad'),(self.cs+[candidates('d'*64,'b'*64)[2]],'c'*64)):
            with self.assertRaises(ValueError):build_learning_lab_preview(cs,pin)
    def test_hash_determinism_input_preserved_and_source_only_context(self):
        before=copy.deepcopy(self.cs)
        a=build_learning_lab_preview(self.cs,'c'*64,source_head='d'*40)
        self.assertEqual(a,build_learning_lab_preview(self.cs,'c'*64,source_head='d'*40))
        self.assertEqual(self.cs,before);self.assertFalse(a['source_admitted'])
        self.assertNotEqual(a['preview_sha256'],build_learning_lab_preview(self.cs,'e'*64,source_head='d'*40)['preview_sha256'])
    def test_hostile_nested_and_authority_claims_rejected(self):
        cs=copy.deepcopy(self.cs);cs[0]['promotion_allowed']=True
        with self.assertRaises(ValueError):build_learning_lab_preview(cs,'c'*64)
        with self.assertRaises(ValueError):build_learning_lab_preview(object(),'c'*64)



class EngineReadbackChecks(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'result.json'
    def tearDown(self):self.tmp.cleanup()
    def fixture(self):
        from mwi_offline.evaluation import digest
        s=candidates('a'*64,'b'*64)[0]
        stat=dict(net_pnl=0.,fees=0,trades=0,profit_factor=None,closed_trade_drawdown=0.,refused=0,wait=1,expectancy=None,
                  results=[{'status':'WAIT','reason':'BASELINE_WAIT'}],fills_scope='MODELED_OHLC_NOT_ACTUAL_EXCHANGE',mfe_mae='UNAVAILABLE_INTRABAR_PATH',funding='EXPLICIT_SYNTHETIC_ZERO_ASSUMPTION',partial_fills='UNSUPPORTED')
        metric=dict(n=1,brier_sum=.5,log_loss=.7,accuracy=0.,ece_top_label=.5,reliability=[{'bin':5,'n':1,'confidence':.5,'accuracy':0.}],class_counts={'BREAKOUT':1,'BOUNCE':0,'TIMEOUT':0})
        errors={'baseline':copy.deepcopy(metric),'graph':copy.deepcopy(metric)}
        config=dict(schema='mwi.synthetic.finite-cycle.v1',dataset_id='a'*64,source_head='c'*40,source_hash='d'*64,
                    simulator_sha256='99c1a3a7907b0481c0f2a4f239fb6808f137834b39fffaf7885ef60f66246832',
                    binding_scope='PINNED_EXISTING_PURE_SIMULATOR_SYNTHETIC_DEVELOPER_ONLY',max_candidates=6,max_iterations=2,development_only=True,promotion_allowed=False,policy_holdout_bars=1800,policy_holdout_seed=20261113,policy_holdout_start_ms=60000)
        hold=dict(seed=20261113,dataset_id='e'*64,start_ms=60000,end_ms=108060000,selection_used_holdout=False,frozen_strategy_id=s['strategy_id'],scope='FRESH_SYNTHETIC_REALIZATION_NOT_EMPIRICAL_MARKET_OOS',base=copy.deepcopy(stat),stress=copy.deepcopy(stat),forecast_errors=copy.deepcopy(errors))
        return dict(status='SYNTHETIC_FINITE_FEEDBACK_COMPLETE',config=config,evaluated_candidates=1,iterations=1,candidates=[{'strategy':s,'base':copy.deepcopy(stat),'stress':copy.deepcopy(stat),'evaluation_scope':'DEVELOPMENT_ONLY_NOT_FINAL_OOS'}],selected_strategy_id=s['strategy_id'],policy_holdout=hold,forecast_errors=errors,original_final_oos='NOT_USED_FOR_SELECTION',candidate_state='RESEARCH_CANDIDATE_ONLY',promotion_allowed=False,model_registry='IMMUTABLE_MODEL_ARTIFACT_ONLY_OWNER_REGISTRY_NOT_CONNECTED',math_integration='PENDING_OWNER_CONTRACT',terminan_integration='PENDING_OWNER_API',real_data='NOT_ADMITTED',rl='BLOCKED_SIMULATOR_FIDELITY_AND_DATA')
    def readback(self,r):
        import json,hashlib
        from mwi_offline.learning_lab import inspect_engine_result
        raw=json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode();self.path.write_bytes(raw)
        return inspect_engine_result(self.path,hashlib.sha256(raw).hexdigest(),'c'*40)
    def test_exact_domains_actual_wait_and_unknown_not_fake_progress(self):
        out=self.readback(self.fixture());d=out['domains']
        self.assertEqual(set(d),{'dataset_readiness','model_versions','training_progress','strategy_candidates','oos_results','simulated_pnl_and_risk','forecast_probabilities','mwi_graph_visualizations','experiment_lineage'})
        self.assertEqual(d['simulated_pnl_and_risk']['data'][0]['base']['wait'],1)
        self.assertEqual(d['simulated_pnl_and_risk']['data'][0]['base']['reason_counts'],{'BASELINE_WAIT':1})
        self.assertIsNone(d['training_progress']['data']);self.assertIsNone(d['forecast_probabilities']['data']);self.assertIsNone(d['mwi_graph_visualizations']['data'])
        self.assertFalse(out['authenticated']);self.assertFalse(out['training_authorized'])
        self.assertEqual(d['oos_results']['data']['scope'],'FRESH_SYNTHETIC_REALIZATION_NOT_EMPIRICAL_MARKET_OOS')
    def test_pin_source_schema_candidate_and_join_refusals(self):
        from mwi_offline.learning_lab import inspect_engine_result
        self.readback(self.fixture())
        with self.assertRaises(ValueError):inspect_engine_result(self.path,'0'*64,'c'*40)
        with self.assertRaises(ValueError):inspect_engine_result(self.path,__import__('hashlib').sha256(self.path.read_bytes()).hexdigest(),'f'*40)
        for change in (lambda r:r.update(evaluated_candidates=2),lambda r:r.update(live=True),lambda r:r['config'].update(promotion_allowed=True),lambda r:r['policy_holdout'].update(frozen_strategy_id='f'*64),lambda r:r['candidates'][0]['strategy'].update(model_hash='x'),lambda r:r['candidates'][0]['base'].update(wait=0),lambda r:r['forecast_errors']['baseline'].update(accuracy=float('inf'))):
            r=self.fixture();change(r)
            with self.assertRaises(ValueError):self.readback(r)
    def test_malformed_raw_bounds_duplicates_and_nonfinite(self):
        import hashlib
        from mwi_offline.learning_lab import inspect_engine_result
        for raw in (b'{"x":1,"x":2}',b'['*65+b']'*65,b'{"x":NaN}',b' '*(1024*1024+1)):
            self.path.write_bytes(raw)
            with self.assertRaises(ValueError):inspect_engine_result(self.path,hashlib.sha256(raw).hexdigest(),'c'*40)
    def test_negative_pnl_retained_not_filtered(self):
        r=self.fixture();s=candidates('a'*64,'b'*64)[1];r['candidates'][0]['strategy']=s
        r['selected_strategy_id']=s['strategy_id'];r['policy_holdout']['frozen_strategy_id']=s['strategy_id']
        def negative(scenario):
            trade=dict(net_pnl=-1.,gross_pnl=-.9,fees=.1,entry_time=120000,exit_time=120000,entry_price=100.,exit_price=99.1,side='long',exit_reason='SL',metadata=dict(strategy_id=s['strategy_id'],example_id='TOYUSDT:60000',scope='SYNTHETIC_SCENARIO'))
            row=dict(status='SIMULATED',trade=trade,strategy_id=s['strategy_id'],simulator_sha256=r['config']['simulator_sha256'],binding_scope=r['config']['binding_scope'],funding='SYNTHETIC_ZERO_ASSUMPTION_NOT_OBSERVED',depth_partial_fills='UNSUPPORTED',cost_scenario=scenario,risk_scope='EX_ANTE_STOP_ESTIMATE_NOT_GAP_LOSS_GUARANTEE')
            v=copy.deepcopy(r['candidates'][0]['base']);v.update(net_pnl=-1.,fees=.1,trades=1,profit_factor=0.,closed_trade_drawdown=.001,wait=0,expectancy=-1.,results=[row]);return v
        r['candidates'][0]['base']=negative('BASE');r['candidates'][0]['stress']=negative('STRESS')
        out=self.readback(r)
        self.assertEqual(out['domains']['simulated_pnl_and_risk']['data'][0]['base']['net_pnl'],-1.)
        r['candidates'][0]['base']['net_pnl']=-2.
        with self.assertRaises(ValueError):self.readback(r)


    def simulated_fixture(self):
        r=self.fixture();c=candidates('a'*64,'b'*64)[1]
        r['candidates'][0]['strategy']=c;r['selected_strategy_id']=c['strategy_id'];r['policy_holdout']['frozen_strategy_id']=c['strategy_id']
        for scenario in ('BASE','STRESS'):
            t=dict(net_pnl=-1.,gross_pnl=-.9,fees=.1,entry_time=120000,exit_time=120000,entry_price=100.,exit_price=99.1,side='long',exit_reason='SL',metadata=dict(strategy_id=c['strategy_id'],example_id='TOYUSDT:60000',scope='SYNTHETIC_SCENARIO'))
            row=dict(status='SIMULATED',trade=t,strategy_id=c['strategy_id'],simulator_sha256=r['config']['simulator_sha256'],binding_scope=r['config']['binding_scope'],funding='SYNTHETIC_ZERO_ASSUMPTION_NOT_OBSERVED',depth_partial_fills='UNSUPPORTED',cost_scenario=scenario,risk_scope='EX_ANTE_STOP_ESTIMATE_NOT_GAP_LOSS_GUARANTEE')
            v=copy.deepcopy(r['candidates'][0]['base']);v.update(net_pnl=-1.,fees=.1,trades=1,profit_factor=0.,closed_trade_drawdown=.001,wait=0,expectancy=-1.,results=[row])
            r['policy_holdout'][scenario.lower()]=v
        return r
    def test_metrics_reject_out_of_range_or_inconsistent_calibration(self):
        for change in (lambda v:v.update(brier_sum=3.),lambda v:v.update(accuracy=1.),lambda v:v.update(ece_top_label=0.),lambda v:v['reliability'][0].update(bin=2),lambda v:v['reliability'][0].update(accuracy=.5)):
            r=self.fixture();change(r['forecast_errors']['baseline'])
            with self.assertRaises(ValueError):self.readback(r)
    def test_holdout_trades_and_episodes_join_declared_window(self):
        self.readback(self.simulated_fixture())
        for change in (lambda h:h.update(start_ms=120000,end_ms=108120000),lambda h:h['base']['results'][0]['trade'].update(exit_time=108060000),lambda h:h['base']['results'][0]['trade']['metadata'].update(example_id='TOYUSDT:0'),lambda h:h['base']['results'][0]['trade'].update(exit_time=900000)):
            r=self.simulated_fixture();change(r['policy_holdout'])
            r['config']['policy_holdout_start_ms']=r['policy_holdout']['start_ms']
            with self.assertRaises(ValueError):self.readback(r)
    def test_native_gap_exit_reasons_are_valid_but_unknown_reasons_refused(self):
        for reason in ('SL_GAP','TP_GAP'):
            r=self.simulated_fixture();r['policy_holdout']['base']['results'][0]['trade']['exit_reason']=reason
            self.readback(r)
        r=self.simulated_fixture();r['policy_holdout']['base']['results'][0]['trade']['exit_reason']='INVENTED'
        with self.assertRaises(ValueError):self.readback(r)

class CommittedFixtureTests(unittest.TestCase):
    def test_raw_pins_and_projection_module_match_committed_fixture(self):
        import hashlib
        import json
        root=Path(__file__).resolve().parents[3]
        directory=root/'artifacts/mwi/learning-lab/v1'
        manifest=json.loads((directory/'manifest.json').read_bytes())
        for key in ('fixture','fixture_schema'):
            ref=manifest[key];raw=(directory/ref['file']).read_bytes()
            self.assertEqual(len(raw),ref['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),ref['sha256'])
        raw=(root/'research/mwi_offline/mwi_offline/learning_lab.py').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),manifest['projection_module_sha256'])
        fixture=json.loads((directory/manifest['fixture']['file']).read_bytes())
        self.assertEqual(fixture['input_result']['raw_sha256'],manifest['input_result']['raw_sha256'])
        self.assertEqual(fixture['input_result']['byte_count'],manifest['input_result']['bytes'])
        self.assertEqual(fixture['source_head'],manifest['input_result']['source_head'])


    def test_native_mean_confidence_boundary_roundoff_is_accepted(self):
        from mwi_offline.learning_lab import _metric
        v=dict(n=3,brier_sum=.1,log_loss=.2,accuracy=1.,ece_top_label=1.-sum([.7]*3)/3,
               reliability=[dict(bin=7,n=3,confidence=sum([.7]*3)/3,accuracy=1.)],
               class_counts={'BREAKOUT':3,'BOUNCE':0,'TIMEOUT':0})
        self.assertEqual(_metric(v)['n'],3)
        v['reliability'][0]['bin']=2
        with self.assertRaises(ValueError):_metric(v)

if __name__=='__main__':unittest.main(verbosity=2)
