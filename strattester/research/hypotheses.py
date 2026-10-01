from dataclasses import dataclass

@dataclass(frozen=True)
class SMCHypothesis:
    id:str
    required_features:tuple[str,...]
    bias_timeframe:str|None
    setup_timeframe:str
    entry_timeframe:str

def build_smc_hypotheses(*,bias_timeframe='1h',setup_timeframe='15m',entry_timeframe='5m'):
    def h(id,features,bias=bias_timeframe):
        return SMCHypothesis(id,tuple(features),bias,setup_timeframe,entry_timeframe)
    return (
        h('SMC_SWEEP_ONLY',('liquidity_sweep',),None),
        h('SMC_CHOCH_ONLY',('choch',),None),
        h('SMC_OB_ONLY',('order_block',),None),
        h('SMC_FVG_ONLY',('fvg',),None),
        h('SMC_HTF_BIAS_LTF_SWEEP',('liquidity_sweep',)),
        h('SMC_HTF_OB_LTF_CHOCH',('order_block','choch')),
        h('SMC_HTF_OB_FVG',('order_block','fvg')),
        h('SMC_SWEEP_BOS',('liquidity_sweep','bos'),None),
        h('SMC_SWEEP_CHOCH_FVG',('liquidity_sweep','choch','fvg'),None),
        h('SMC_NO_HTF_CONTROL',('liquidity_sweep','choch'),None),
    )
