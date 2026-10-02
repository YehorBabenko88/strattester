from .research_common import HypothesisSpec

def smc_hypotheses():
    return (
      HypothesisSpec('SMC_CONTROL_MOMENTUM','smc',{'setup':'momentum'},True),
      HypothesisSpec('SMC_OB','smc',{'setup':'order_block'}),
      HypothesisSpec('SMC_OB_FVG','smc',{'setup':'order_block','confirm':'fvg'}),
      HypothesisSpec('SMC_OB_BOS','smc',{'setup':'order_block','confirm':'bos'}),
      HypothesisSpec('SMC_SWEEP_BOS','smc',{'setup':'liquidity_sweep','confirm':'bos'}),
      HypothesisSpec('SMC_HTF_BIAS_LTF_SWEEP','smc',{'bias_timeframes':('4h','1h'),'entry_timeframes':('15m','5m','1m'),'setup':'liquidity_sweep'}),
    )
