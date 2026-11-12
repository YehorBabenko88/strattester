"""Pure bounded candidate admission preparation; no execution or promotion."""
import copy
import math
from .evaluation import digest
from .strategy import validate


def _plain(value, depth=0, remaining=None):
    if remaining is None: remaining = [4096]
    remaining[0] -= 1
    if remaining[0] < 0: raise ValueError('DECLARATION_WORK_BUDGET')
    if depth > 8:
        raise ValueError('DECLARATION_DEPTH')
    if type(value) is dict:
        if len(value) > 32 or any(type(k) is not str or len(k)>128 for k in value):
            raise ValueError('DECLARATION_KEYS')
        for item in value.values(): _plain(item, depth+1, remaining)
    elif type(value) is list:
        if len(value) > 32: raise ValueError('DECLARATION_SIZE')
        for item in value: _plain(item, depth+1, remaining)
    elif type(value) not in (str, int, float, bool, type(None)):
        raise ValueError('DECLARATION_TYPE')
    elif type(value) is str and len(value) > 256:
        raise ValueError('DECLARATION_SIZE')
    elif type(value) is float and not math.isfinite(value):
        raise ValueError('FINITE_DECLARATION')
    elif type(value) is int and abs(value)>2**53-1:
        raise ValueError('INTEGER_DECLARATION')


def prepare_search(declarations, budget):
    """Retain every bounded input outcome, including failures and duplicates.

    Budget caps accepted unique declarations; this does not reserve native jobs.
    Noncanonical/unbounded input is refused before a batch identity is created;
    bounded JSON-compatible invalid declarations are retained as refusal records.
    Existing feedback cycle owns execution/checkpoint/holdout, unchanged here.
    """
    if type(budget) is not int or not 1 <= budget <= 6:
        raise ValueError('FIXED_SEARCH_BUDGET')
    if type(declarations) is not list or not 1 <= len(declarations) <= 6:
        raise ValueError('BOUNDED_DECLARATIONS')
    _plain(declarations)
    accepted, records, seen = [], [], {}
    for index, declaration in enumerate(declarations):
        try:
            validate(declaration)
        except (ValueError, TypeError, KeyError) as exc:
            records.append({'index': index, 'status': 'VALIDATION_REFUSED', 'reason': str(exc),
                            'declaration': copy.deepcopy(declaration)})
            continue
        semantic = {k: v for k, v in declaration.items()
                    if k not in ('strategy_id', 'version', 'parent_id')}
        if declaration['family'] in ('wait', 'bounce_rule'):
            semantic.pop('threshold')  # ignored by existing strategy.propose
        key = digest(semantic)
        record = {'index': index, 'strategy_id': declaration['strategy_id'], 'semantic_hash': key}
        if key in seen:
            record.update(status='DUPLICATE', duplicate_of=seen[key])
        elif len(accepted) >= budget:
            record.update(status='BUDGET_REFUSED')
        else:
            seen[key] = declaration['strategy_id']
            accepted.append(copy.deepcopy(declaration))
            record.update(status='ACCEPTED')
        records.append(record)
    result = {'schema': 'mwi.search.preparation.v1', 'status': 'LOCAL_PREPARATION_ONLY',
              'budget': budget, 'mode': 'SIMULATION_ONLY', 'promotion_allowed': False,
              'candidates': accepted, 'records': records}
    return dict(result, preparation_hash=digest(result))
