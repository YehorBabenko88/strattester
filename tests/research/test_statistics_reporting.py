from types import SimpleNamespace
from strattester.research.statistics import evaluate_trades
from strattester.research.reporting import research_report

def T(net,gross,fees,entry,exit,coverage='COMPLETE_HISTORY',vol='NORMAL',mae=0,mfe=0,r=0):
    return SimpleNamespace(net_pnl=net,gross_pnl=gross,fees=fees,entry_time=entry,exit_time=exit,
        metadata={'coverage':coverage,'volatility':vol,'mae':mae,'mfe':mfe,'r_multiple':r})

def test_statistics_compute_core_metrics_drawdown_and_streaks():
    xs=[T(2,2.2,.2,0,60,mae=-.5,mfe=3,r=1),T(-1,-.8,.2,60,180,mae=-2,mfe=.2,r=-.5),T(-2,-1.8,.2,180,240,mae=-3,mfe=.1,r=-1)]
    m=evaluate_trades(xs)
    assert m.trades==3 and m.wins==1 and m.losses==2
    assert round(m.win_rate,6)==round(1/3,6)
    assert m.net_pnl==-1 and round(m.fees,10)==.6
    assert m.expectancy==-1/3
    assert m.profit_factor==2/3
    assert m.max_drawdown==3
    assert m.max_consecutive_losses==2
    assert m.avg_holding_ms==80
    assert m.avg_mae<0 and m.avg_mfe>0

def test_primary_report_excludes_partial_history():
    xs=[T(2,2,0,0,1,'COMPLETE_HISTORY','HIGH'),T(100,100,0,0,1,'PARTIAL_HISTORY','HIGH')]
    r=research_report(xs)
    assert r.primary.trades==1 and r.primary.net_pnl==2
    assert r.partial.trades==1 and r.partial.net_pnl==100

def test_volatility_breakdown_keeps_sample_counts_and_coverage_separate():
    xs=[T(2,2,0,0,1,'COMPLETE_HISTORY','HIGH'),T(-1,-1,0,0,1,'COMPLETE_HISTORY','LOW'),T(3,3,0,0,1,'PARTIAL_HISTORY','HIGH')]
    r=research_report(xs)
    assert r.by_volatility['HIGH'].trades==1
    assert r.by_volatility['LOW'].trades==1
    assert r.partial_by_volatility['HIGH'].trades==1

def test_adversarial_partial_history_cannot_contaminate_primary_metrics():
    """
    End-to-end statistical isolation test.

    Trades are produced by the real execution simulator.  PARTIAL_HISTORY
    trades are deliberately made extremely profitable / extremely losing.
    Neither is allowed to alter any primary COMPLETE_HISTORY statistic.
    """
    from dataclasses import asdict

    from strattester.research.execution import (
        ExecutionPolicy,
        Signal,
        simulate_trade,
    )

    def bar(t,o,h,l,c):
        return {
            "t":t,
            "open":o,
            "high":h,
            "low":l,
            "close":c,
        }

    policy=ExecutionPolicy(
        bar_ms=60,
        fee_rate=0.0,
        slippage_bps=0.0,
        position_usd=100.0,
    )

    # COMPLETE_HISTORY winner: +5 USD.
    complete_win=simulate_trade(
        Signal(
            decision_time=60,
            side="long",
            entry_kind="market",
            entry_price=None,
            stop_loss=95,
            take_profit=105,
        ),
        [
            bar(0,100,101,99,100),
            bar(60,100,101,99,100),
            bar(120,100,106,99,105),
        ],
        policy,
        metadata={
            "coverage":"COMPLETE_HISTORY",
            "volatility":"NORMAL",
        },
    )

    # COMPLETE_HISTORY loser: -2 USD.
    complete_loss=simulate_trade(
        Signal(
            decision_time=240,
            side="long",
            entry_kind="market",
            entry_price=None,
            stop_loss=98,
            take_profit=105,
        ),
        [
            bar(180,100,101,99,100),
            bar(240,100,101,99,100),
            bar(300,100,101,97,98),
        ],
        policy,
        metadata={
            "coverage":"COMPLETE_HISTORY",
            "volatility":"NORMAL",
        },
    )

    baseline=research_report([
        complete_win,
        complete_loss,
    ])

    baseline_primary=asdict(
        baseline.primary
    )

    assert baseline.primary.trades==2
    assert baseline.primary.wins==1
    assert baseline.primary.losses==1
    assert baseline.primary.net_pnl==3.0
    assert baseline.primary.expectancy==1.5

    # Partial-history trade with an intentionally enormous gain.
    # Position size is enlarged so contamination would be obvious.
    huge_policy=ExecutionPolicy(
        bar_ms=60,
        fee_rate=0.0,
        slippage_bps=0.0,
        position_usd=100_000.0,
    )

    partial_huge_win=simulate_trade(
        Signal(
            decision_time=420,
            side="long",
            entry_kind="market",
            entry_price=None,
            stop_loss=50,
            take_profit=200,
        ),
        [
            bar(360,100,101,99,100),
            bar(420,100,101,99,100),
            bar(480,100,201,99,200),
        ],
        huge_policy,
        metadata={
            "coverage":"PARTIAL_HISTORY",
            "volatility":"EXTREME",
            "data_quality":"GAP_PRESENT",
        },
    )

    with_partial_win=research_report([
        complete_win,
        complete_loss,
        partial_huge_win,
    ])

    # Exact equality across the complete TradeMetrics dataclass means
    # trades/wins/losses/win-rate/PnL/fees/expectancy/PF/drawdown and
    # every currently defined primary metric remain uncontaminated.
    assert asdict(
        with_partial_win.primary
    )==baseline_primary

    assert with_partial_win.partial.trades==1
    assert with_partial_win.partial.wins==1
    assert with_partial_win.partial.net_pnl>50_000

    assert "EXTREME" not in with_partial_win.by_volatility
    assert (
        with_partial_win
        .partial_by_volatility["EXTREME"]
        .trades
        ==1
    )

    # Now replace the huge partial winner with a catastrophic partial loss.
    partial_huge_loss=simulate_trade(
        Signal(
            decision_time=600,
            side="long",
            entry_kind="market",
            entry_price=None,
            stop_loss=50,
            take_profit=200,
        ),
        [
            bar(540,100,101,99,100),
            bar(600,100,101,99,100),
            bar(660,40,41,39,40),
        ],
        huge_policy,
        metadata={
            "coverage":"PARTIAL_HISTORY",
            "volatility":"EXTREME",
            "data_quality":"GAP_PRESENT",
        },
    )

    with_partial_loss=research_report([
        complete_win,
        complete_loss,
        partial_huge_loss,
    ])

    assert asdict(
        with_partial_loss.primary
    )==baseline_primary

    assert with_partial_loss.partial.trades==1
    assert with_partial_loss.partial.losses==1
    assert with_partial_loss.partial.net_pnl<-50_000

    # Winner + loser together must still have zero influence on primary.
    both=research_report([
        complete_win,
        complete_loss,
        partial_huge_win,
        partial_huge_loss,
    ])

    assert asdict(
        both.primary
    )==baseline_primary

    assert both.partial.trades==2
    assert both.partial.wins==1
    assert both.partial.losses==1

    assert (
        both.partial_by_volatility["EXTREME"].trades
        ==2
    )


def test_unknown_or_unclassified_history_is_never_primary():
    """
    Fail closed: missing/unknown coverage must not silently enter primary
    COMPLETE_HISTORY statistics.
    """
    unknown=T(
        1_000_000,
        1_000_000,
        0,
        0,
        1,
        coverage="UNKNOWN",
        vol="EXTREME",
    )

    missing_metadata=T(
        -1_000_000,
        -1_000_000,
        0,
        0,
        1,
        coverage="COMPLETE_HISTORY",
        vol="EXTREME",
    )

    # Remove coverage entirely rather than assigning a recognized class.
    missing_metadata.metadata.pop(
        "coverage"
    )

    report=research_report([
        unknown,
        missing_metadata,
    ])

    assert report.primary.trades==0
    assert report.partial.trades==0
    assert report.primary.net_pnl==0.0
    assert report.primary.expectancy==0.0
