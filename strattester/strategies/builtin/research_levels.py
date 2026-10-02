from .research_common import HypothesisSpec

def level_hypotheses():
    return (
      HypothesisSpec('LEVEL_BASE','levels',{} ,True),
      HypothesisSpec('LEVEL_VOLUME','levels',{'confirm':'volume'}),
      HypothesisSpec('LEVEL_OI','levels',{'confirm':'open_interest'}),
      HypothesisSpec('LEVEL_POC','levels',{'confirm':'poc'}),
      HypothesisSpec('LEVEL_BREAKOUT_RETEST','levels',{'setup':'breakout_retest'}),
    )
