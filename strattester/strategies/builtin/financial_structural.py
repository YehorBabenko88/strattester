"""Explicit research-only registry entry. No mutable store or exchange capability."""
from dataclasses import dataclass,asdict
from strattester.strategies.base import StrategyDefinition,strategy_fingerprint
from strattester.strategies.registry import StrategyRegistry
from strattester.engine.executor import StrategyResult
from strattester.research.financial_attested_inference import AttestedInferenceRequest,run_attested_offline
from strattester.research.financial_signed_export import ExportPolicy
from strattester.research.financial_signatures import OpenSSLVerifier


@dataclass(frozen=True,slots=True)
class FinancialResearchContext:
    request: AttestedInferenceRequest
    policy: ExportPolicy
    verifier: OpenSSLVerifier


class FinancialStructuralResearch:
    id='FINANCIAL_STRUCTURAL_RESEARCH'
    version='0.2.0'
    requirements=()

    def run_context(self,context,checkpoint=None):
        if type(context) is not FinancialResearchContext or checkpoint is not None:
            raise ValueError('offline financial research context required; mutable store execution prohibited')
        result=run_attested_offline(context.request,policy=context.policy,verifier=context.verifier)
        return {'mode':'OFFLINE_RESEARCH_ONLY','status':'RESEARCH_PREDICTION','trades':[],
                'prediction':asdict(result.prediction),'provenance':result.provenance}


def register_financial_research(registry,*,research_only=False):
    if research_only is not True or type(registry) is not StrategyRegistry:
        raise ValueError('explicit research-only registry required')
    definition=StrategyDefinition(FinancialStructuralResearch.id,FinancialStructuralResearch.version,(),
        FinancialStructuralResearch,enabled=False,feature_versions=('signed_snapshot_v1','financial_equations_v2'))
    registry.register(definition)
    return definition


def execute_financial_research(registry,context,*,research_only=False):
    if research_only is not True or type(registry) is not StrategyRegistry:
        raise ValueError('explicit research-only execution required')
    found=[d for d in registry.discover() if (d.id,d.version)==(FinancialStructuralResearch.id,FinancialStructuralResearch.version)]
    if len(found)!=1 or found[0].implementation is not FinancialStructuralResearch:
        raise ValueError('registered financial research implementation required')
    definition=found[0]
    if definition.enabled is not True:raise ValueError('financial research strategy disabled; explicit enable required')
    output=FinancialStructuralResearch().run_context(context)
    return StrategyResult(definition.id,definition.version,strategy_fingerprint(definition),output)

