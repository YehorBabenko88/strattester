"""Contract-only fixtures, never executed Math owner results."""
import copy
import hashlib
import json
import sys
import unittest
from mwi_offline.math_contract import prepare_request, validate_result, SOURCE_SHA, SOURCE_HEAD


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def request(operation='difference'):
    return dict(schema='mwi.math.feature.request.v1',dataset_id='synthetic-fixture',dataset_hash='a'*64,
                feature_version='toy-contract-v1',decision_cutoff=180001,transform_source_sha=SOURCE_SHA,
                math_source_head=SOURCE_HEAD,operation=operation,parameters={'order':1} if operation=='difference' else {'window':30},
                unit='USDT/BTC',semantic_kind='price',interval_ms=60000,
                points=[dict(event_start=0,event_end=60000,availability_timestamp=60001,value=100.),
                        dict(event_start=60000,event_end=120000,availability_timestamp=120001,value=102.),
                        dict(event_start=120000,event_end=180000,availability_timestamp=180001,value=101.)],
                missingness=[False,False,False])


def expected_unexecuted_result(prepared):
    r=prepared['request']
    out=dict(schema='mwi.math.feature.result.v1',dataset_id=r['dataset_id'],dataset_hash=r['dataset_hash'],
             feature_version=r['feature_version'],decision_cutoff=r['decision_cutoff'],
             availability_timestamp=180001,transform_source_sha=SOURCE_SHA,math_source_head=SOURCE_HEAD,
             operation=r['operation'],parameters=r['parameters'],input_prefix_hash=prepared['input_prefix_hash'],
             request_hash=prepared['request_hash'],unit=r['unit'],semantic_kind='difference',
             values=[2.,-1.],event_timestamps=[120000,180000],availability_timestamps=[120001,180001],
             missingness=[False,False],math_valid_flags={'finite_output':True,'full_window_ready':True},
             execution_authority=False,training_authorized=False,trading_authorized=False)
    out['output_hash']=digest(out)
    return out


class MathContractTests(unittest.TestCase):
    def test_preparation_only_identity(self):
        before=set(sys.modules);r=request();p=prepare_request(r)
        self.assertEqual(p['status'],'EXECUTION_BLOCKED')
        self.assertEqual(p['request']['dataset_hash'],'a'*64)
        self.assertNotEqual(p['input_prefix_hash'],r['dataset_hash'])
        self.assertEqual(p['availability_timestamp'],180001)
        self.assertFalse(p['math_valid_flags']['numerically_executed'])
        self.assertEqual(set(sys.modules),before)

    def test_prefix_hash_separate_from_full_dataset(self):
        a=request();b=copy.deepcopy(a);b['dataset_hash']='b'*64
        x,y=prepare_request(a),prepare_request(b)
        self.assertEqual(x['input_prefix_hash'],y['input_prefix_hash'])
        self.assertNotEqual(x['request_hash'],y['request_hash'])

    def test_only_two_fixed_operations(self):
        self.assertEqual(prepare_request(request('rolling_volatility'))['status'],'EXECUTION_BLOCKED')
        for key,value in [('operation','volatility_regime'),('parameters',{'order':2}),('transform_source_sha','b'*64),('math_source_head','c'*40)]:
            r=request();r[key]=value
            with self.assertRaises(ValueError):prepare_request(r)

    def test_clock_gap_duplicate_and_lookahead_refused(self):
        for field,value in [('event_start',1),('event_end',120000),('availability_timestamp',180002),('availability_timestamp',0)]:
            r=request();r['points'][0][field]=value
            with self.assertRaises(ValueError):prepare_request(r)

    def test_unknown_clocks_and_nonfinite_values_refused(self):
        for field,value in [('value',float('nan')),('value',True),('availability_timestamp',None),('availability_timestamp',True)]:
            r=request();r['points'][0][field]=value
            with self.assertRaises(ValueError):prepare_request(r)

    def test_missingness_not_zero_filled(self):
        r=request();r['points'][0]['value']=None;r['missingness'][0]=True
        with self.assertRaises(ValueError):prepare_request(r)
        r['missingness'][0]=False
        with self.assertRaises(ValueError):prepare_request(r)

    def test_known_zero_preserved(self):
        r=request();r['points'][0]['value']=0.
        self.assertEqual(prepare_request(r)['request']['points'][0]['value'],0.)

    def test_unknown_fields_and_bounds(self):
        r=request();r['runtime_grant']=True
        with self.assertRaises(ValueError):prepare_request(r)
        r=request();r['points']*=1000;r['missingness']*=1000
        with self.assertRaises(ValueError):prepare_request(r)
        class Evil(dict):pass
        with self.assertRaises(ValueError):prepare_request(Evil(request()))

    def test_prepared_snapshot_not_aliased(self):
        r=request();p=prepare_request(r);r['points'][0]['value']=999.
        self.assertEqual(p['request']['points'][0]['value'],100.)

    def test_unexecuted_owner_fixture_is_only_schema_valid(self):
        p=prepare_request(request());r=expected_unexecuted_result(p)
        receipt=validate_result(r,p)
        self.assertEqual(receipt['status'],'EXECUTION_BLOCKED')
        self.assertTrue(receipt['result_schema_valid'])
        self.assertFalse(receipt['numerical_validity_verified'])

    def test_result_hash_lineage_and_dependency_clocks(self):
        p=prepare_request(request())
        for field,value in [('output_hash','0'*64),('dataset_hash','b'*64),('availability_timestamps',[60001,180001]),('event_timestamps',[60000,180000]),('execution_authority',True)]:
            r=expected_unexecuted_result(p);r[field]=value
            if field!='output_hash':r['output_hash']=digest({k:v for k,v in r.items() if k!='output_hash'})
            with self.assertRaises(ValueError):validate_result(r,p)


    def test_rolling_result_is_not_numerically_verified_and_warmup_is_visible(self):
        p=prepare_request(request('rolling_volatility'));r=expected_unexecuted_result(p)
        # Arbitrary finite placeholder CLAIM, not an executed/validated transform.
        r.update(values=[123.,123.],event_timestamps=[120000,180000],
                 availability_timestamps=[120001,180001],missingness=[False]*2,
                 semantic_kind='rolling_volatility',math_valid_flags={'finite_output':True,'full_window_ready':False})
        r['output_hash']=digest({k:v for k,v in r.items() if k!='output_hash'})
        receipt=validate_result(r,p)
        self.assertFalse(receipt['numerical_validity_verified'])
        self.assertEqual(receipt['warmup_mask'],[True]*2)

    def test_result_parameter_types_are_exact(self):
        p=prepare_request(request());r=expected_unexecuted_result(p)
        r['parameters']={'order':True}
        r['output_hash']=digest({k:v for k,v in r.items() if k!='output_hash'})
        with self.assertRaises(ValueError):validate_result(r,p)

    def test_a7_input_output_magnitude_bounds(self):
        for value in (1e12+1,-1e12-1):
            r=request();r['points'][0]['value']=value
            with self.assertRaises(ValueError):prepare_request(r)
        p=prepare_request(request());r=expected_unexecuted_result(p)
        r['values'][0]=2e12+1;r['output_hash']=digest({k:v for k,v in r.items() if k!='output_hash'})
        with self.assertRaises(ValueError):validate_result(r,p)

    def test_a7_prices_only_and_two_original_records(self):
        for kind in ('price_difference','simple_return','log_return'):
            r=request('rolling_volatility');r['semantic_kind']=kind
            if kind!='price_difference':r['unit']='dimensionless'
            with self.assertRaises(ValueError):prepare_request(r)
        r=request('rolling_volatility');r['points']=r['points'][:1];r['missingness']=[False]
        with self.assertRaises(ValueError):prepare_request(r)

    def test_rolling_keeps_original_predecessor_availability(self):
        r=request('rolling_volatility');r['points'][0]['availability_timestamp']=180001
        p=prepare_request(r);claim=expected_unexecuted_result(p)
        claim.update(values=[1.,1.],event_timestamps=[120000,180000],availability_timestamps=[180001,180001],
                     semantic_kind='rolling_volatility',math_valid_flags={'finite_output':True,'full_window_ready':False})
        claim['output_hash']=digest({k:v for k,v in claim.items() if k!='output_hash'})
        self.assertEqual(validate_result(claim,p)['warmup_mask'],[True,True])
        claim['availability_timestamps'][0]=120001
        claim['output_hash']=digest({k:v for k,v in claim.items() if k!='output_hash'})
        with self.assertRaises(ValueError):validate_result(claim,p)

    def test_first_full_rolling_window_requires31_original_prices(self):
        r=request('rolling_volatility')
        r['points']=[dict(event_start=i*60000,event_end=(i+1)*60000,availability_timestamp=(i+1)*60000,value=100.+i) for i in range(31)]
        r['missingness']=[False]*31;r['decision_cutoff']=31*60000
        p=prepare_request(r);claim=expected_unexecuted_result(p)
        claim.update(values=[0.]*30,event_timestamps=[x['event_end'] for x in r['points'][1:]],
                     availability_timestamps=[x['availability_timestamp'] for x in r['points'][1:]],
                     availability_timestamp=31*60000,missingness=[False]*30,semantic_kind='rolling_volatility',
                     math_valid_flags={'finite_output':True,'full_window_ready':True})
        claim['output_hash']=digest({k:v for k,v in claim.items() if k!='output_hash'})
        self.assertEqual(validate_result(claim,p)['warmup_mask'],[True]*29+[False])

if __name__=='__main__':unittest.main(verbosity=2)
