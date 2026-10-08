from __future__ import annotations
from strattester.engine.executor import execute_strategy
from strattester.marketdata.sync_engine import DataRequirement as SyncRequirement,SyncEngine,SyncState
from strattester.marketdata.timeframes import aligned_window


class LifecycleWindowError(RuntimeError):
    pass


def _research_window(
    instrument,
    requested_start,
    requested_end,
    instrument_registry=None,
):
    symbol=instrument['symbol']

    launch=int(
        instrument.get('launchTime')
        or 0
    )

    launch=(
        launch
        // 60_000
    ) * 60_000

    start=(
        launch
        if requested_start is None
        else max(
            launch,
            int(requested_start),
        )
    )

    end=int(requested_end)

    # Exchange metadata provides a useful boundary even when no
    # lifecycle registry has been wired into the caller yet.
    terminal=(
        instrument.get('deliveryTime')
        or instrument.get('delistTime')
    )

    if terminal not in (
        None,
        '',
        0,
        '0',
    ):
        end=min(
            end,
            int(terminal),
        )

    if instrument_registry is None:
        if end < start:
            raise ValueError(
                'end_ms precedes instrument availability'
            )

        return start,end

    intervals=tuple(
        instrument_registry.intervals(
            symbol
        )
    )

    if not intervals:
        raise LifecycleWindowError(
            f'no ACTIVE lifecycle interval for {symbol}'
        )

    intersections=[]

    for interval_start,interval_end in intervals:
        left=max(
            start,
            int(interval_start),
        )

        right=end

        if interval_end is not None:
            # Registry intervals are [start,end), while candle
            # timestamps are discrete observation times.
            right=min(
                right,
                int(interval_end)-1,
            )

        if left <= right:
            intersections.append(
                (left,right)
            )

    if not intersections:
        raise LifecycleWindowError(
            f'requested range is outside ACTIVE lifecycle '
            f'for {symbol}'
        )

    if len(intersections) != 1:
        raise LifecycleWindowError(
            f'requested range crosses multiple ACTIVE lifecycle '
            f'intervals for {symbol}; segmented backtest required'
        )

    active_start,active_end=intersections[0]

    # A continuous research run must not silently skip a suspension
    # before or inside the requested range.
    #
    # Truncation at the final delisting boundary is allowed, but a
    # requested start that lies in a lifecycle gap is not.
    if active_start > start:
        raise LifecycleWindowError(
            f'requested range begins outside ACTIVE lifecycle '
            f'for {symbol}'
        )

    return active_start,active_end


class ResearchRunner:
    def __init__(
        self,
        store,
        client,
        clock_ms=None,
        instrument_registry=None,
    ):
        self.store=store
        self.client=client
        self.clock_ms=clock_ms
        self.instrument_registry=instrument_registry

    def _sync_definition(
        self,
        definition,
        symbol,
        start_ms,
        end_ms,
    ):
        engine=SyncEngine(
            self.store,
            self.client,
            clock_ms=self.clock_ms,
        )

        results=[]

        for req in definition.requirements:
            dataset=getattr(
                req.dataset,
                'value',
                req.dataset,
            )

            for tf in (
                req.timeframes
                or ('1m',)
            ):
                window=aligned_window(
                    start_ms,
                    end_ms,
                    tf,
                )

                if window is None:
                    if req.required:
                        raise LifecycleWindowError(
                            f'ACTIVE research window contains no '
                            f'complete {tf} observation for '
                            f'{dataset}'
                        )

                    continue

                dataset_start,dataset_end=window

                r=engine.sync_requirement(
                    SyncRequirement(
                        symbol,
                        dataset,
                        tf,
                        dataset_start,
                        dataset_end,
                    )
                )

                results.append(
                    (req,r)
                )

                if (
                    req.required
                    and r.state
                    is not SyncState.READY
                ):
                    raise RuntimeError(
                        f'required history not ready: '
                        f'{dataset}/{tf}: '
                        f'{r.state.value} {r.message}'
                        .strip()
                    )

        return tuple(results)

    def run(
        self,
        definition,
        instrument,
        *,
        start_ms:int|None=None,
        end_ms:int,
        checkpoint=None,
    ):
        symbol=instrument['symbol']

        start,end=_research_window(
            instrument,
            start_ms,
            end_ms,
            self.instrument_registry,
        )

        self._sync_definition(
            definition,
            symbol,
            start,
            end,
        )

        return execute_strategy(
            definition,
            self.store,
            symbol,
            checkpoint=checkpoint,
            start_ms=start,
            end_ms=end,
        )
