from .research_common import HypothesisSpec

def poc_hypotheses():
    return (
      HypothesisSpec('POC_MEAN_REVERSION','poc',{'setup':'mean_reversion'}),
      HypothesisSpec('POC_BREAKOUT_RETEST','poc',{'setup':'breakout_retest'}),
      HypothesisSpec('POC_VAH_VAL_REJECTION','poc',{'setup':'value_area_rejection'}),
      HypothesisSpec('POC_MIGRATION','poc',{'setup':'poc_migration'}),
    )
