from .research_common import HypothesisSpec

def volatility_hypotheses():
    return (
      HypothesisSpec('VOL_COMPRESSION_EXPANSION','volatility',{'setup':'compression_expansion'}),
      HypothesisSpec('VOL_EXPANSION_CONTINUATION','volatility',{'setup':'expansion_continuation'}),
      HypothesisSpec('VOL_EXHAUSTION','volatility',{'setup':'exhaustion'}),
    )
