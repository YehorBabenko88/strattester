from .research_common import HypothesisSpec

def smc_hypotheses():
    return (
      HypothesisSpec('SMC_CONTROL_MOMENTUM','smc',{'setup':'momentum'},True),
      HypothesisSpec('SMC_OB','smc',{'setup':'order_block'}),
      HypothesisSpec('SMC_OB_FVG','smc',{'setup':'order_block','confirm':'fvg'}),
      HypothesisSpec('SMC_OB_BOS','smc',{'setup':'order_block','confirm':'bos'}),
      HypothesisSpec('SMC_SWEEP_BOS','smc',{'setup':'liquidity_sweep','confirm':'bos'}),
      HypothesisSpec('SMC_HTF_BIAS_LTF_SWEEP','smc',{'bias_timeframes':('4h','1h'),'entry_timeframes':('15m','5m','1m'),'setup':'liquidity_sweep'}),
      HypothesisSpec('ORDERFLOW_ABSORPTION_PROXY','orderflow',{'setup':'absorption','mode':'ABSORPTION_PROXY','entry_parts':(0.5,0.5),'tp_parts':(0.6,0.4),'requires':('public_trade_aggregates','level','cvd','aggression_decay')}),
      HypothesisSpec('ORDERFLOW_SWEEP_REVERSAL','orderflow',{'setup':'liquidity_sweep_reversal','requires':('level','public_trade_aggregates','cvd'),'return_inside_required':True}),
    )
