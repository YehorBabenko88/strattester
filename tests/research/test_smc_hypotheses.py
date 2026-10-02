from strattester.research.hypotheses import build_smc_hypotheses,SMCHypothesis

def test_smc_suite_contains_mtf_and_ablation_controls():
    xs={x.id:x for x in build_smc_hypotheses()}
    expected={
      'SMC_SWEEP_ONLY','SMC_CHOCH_ONLY','SMC_OB_ONLY','SMC_FVG_ONLY',
      'SMC_HTF_BIAS_LTF_SWEEP','SMC_HTF_OB_LTF_CHOCH','SMC_HTF_OB_FVG',
      'SMC_SWEEP_BOS','SMC_SWEEP_CHOCH_FVG','SMC_NO_HTF_CONTROL'
    }
    assert expected.issubset(xs)
    assert xs['SMC_HTF_BIAS_LTF_SWEEP'].bias_timeframe=='1h'
    assert xs['SMC_HTF_BIAS_LTF_SWEEP'].entry_timeframe=='5m'
    assert xs['SMC_NO_HTF_CONTROL'].bias_timeframe is None

def test_hypotheses_have_explicit_required_features():
    xs={x.id:x for x in build_smc_hypotheses()}
    assert xs['SMC_HTF_OB_LTF_CHOCH'].required_features==('order_block','choch')
    assert xs['SMC_SWEEP_CHOCH_FVG'].required_features==('liquidity_sweep','choch','fvg')

def test_custom_timeframe_ladder_is_supported():
    xs=build_smc_hypotheses(bias_timeframe='4h',setup_timeframe='1h',entry_timeframe='15m')
    x={x.id:x for x in xs}['SMC_HTF_BIAS_LTF_SWEEP']
    assert (x.bias_timeframe,x.setup_timeframe,x.entry_timeframe)==('4h','1h','15m')
