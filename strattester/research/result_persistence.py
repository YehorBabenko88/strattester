from __future__ import annotations
from dataclasses import asdict,is_dataclass

def _metrics(m):
    if is_dataclass(m): d=asdict(m)
    else:
        keys=('trades','wins','losses','win_rate','gross_pnl','net_pnl','fees','expectancy','profit_factor',
              'max_drawdown','avg_mae','avg_mfe','avg_r_multiple','avg_holding_ms','max_consecutive_losses')
        d={k:getattr(m,k) for k in keys if hasattr(m,k)}
    return d

def persist_report(store,run_id,symbol,strategy_result,report):
    metrics=_metrics(report.primary)
    metrics['fingerprint']=strategy_result.fingerprint
    metrics['coverage']='COMPLETE_HISTORY'
    store.put(run_id,symbol,strategy_result.strategy_id,strategy_result.strategy_version,metrics)
    return metrics


def persist_report_fenced(store,stage_id,run_id,symbol,strategy_result,report,lease_validator):
    """Persist scientific output without allowing a stale worker to publish it."""
    metrics=_metrics(report.primary)
    metrics['fingerprint']=strategy_result.fingerprint
    metrics['coverage']='COMPLETE_HISTORY'
    store.stage(stage_id,run_id,symbol,strategy_result.strategy_id,strategy_result.strategy_version,metrics)
    if not store.promote(stage_id,lease_validator):
        raise RuntimeError('result publication fenced: job lease is no longer valid')
    return metrics
