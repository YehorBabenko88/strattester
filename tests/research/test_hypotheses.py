from strattester.strategies.builtin.research_levels import level_hypotheses
from strattester.strategies.builtin.research_smc import smc_hypotheses
from strattester.strategies.builtin.research_poc import poc_hypotheses
from strattester.strategies.builtin.research_volatility import volatility_hypotheses

def test_research_hypothesis_families_have_controls_and_ablations():
    levels={x.name for x in level_hypotheses()}
    smc={x.name for x in smc_hypotheses()}
    poc={x.name for x in poc_hypotheses()}
    vol={x.name for x in volatility_hypotheses()}
    assert {'LEVEL_BASE','LEVEL_VOLUME','LEVEL_OI','LEVEL_POC'}.issubset(levels)
    assert {'SMC_OB','SMC_OB_FVG','SMC_OB_BOS','SMC_SWEEP_BOS','SMC_HTF_BIAS_LTF_SWEEP','SMC_CONTROL_MOMENTUM'}.issubset(smc)
    assert {'POC_MEAN_REVERSION','POC_BREAKOUT_RETEST','POC_VAH_VAL_REJECTION'}.issubset(poc)
    assert {'VOL_COMPRESSION_EXPANSION','VOL_EXPANSION_CONTINUATION','VOL_EXHAUSTION'}.issubset(vol)

def test_smc_mtf_hypothesis_records_bias_and_entry_timeframes():
    x=next(x for x in smc_hypotheses() if x.name=='SMC_HTF_BIAS_LTF_SWEEP')
    assert x.params['bias_timeframes']==('4h','1h')
    assert x.params['entry_timeframes']==('15m','5m','1m')
