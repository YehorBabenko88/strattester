from strattester.marketdata.instruments import InstrumentStatus


class UniverseSnapshotError(RuntimeError):
    pass


class UniverseSynchronizer:
    def __init__(
        self,
        registry,
        client,
        minimum_snapshot_ratio: float = 0.5,
        maximum_missing_ratio: float = 0.2,
        minimum_mass_missing: int = 25,
    ):
        self.registry = registry
        self.client = client
        self.minimum_snapshot_ratio = float(
            minimum_snapshot_ratio
        )
        self.maximum_missing_ratio = float(
            maximum_missing_ratio
        )
        self.minimum_mass_missing = int(
            minimum_mass_missing
        )

        if not 0 <= self.minimum_snapshot_ratio <= 1:
            raise ValueError(
                "minimum_snapshot_ratio must be between 0 and 1"
            )

        if not 0 <= self.maximum_missing_ratio <= 1:
            raise ValueError(
                "maximum_missing_ratio must be between 0 and 1"
            )

        if self.minimum_mass_missing < 1:
            raise ValueError(
                "minimum_mass_missing must be at least 1"
            )

    @staticmethod
    def _rows_by_symbol(rows, expected_status):
        """
        Validate one complete exchange status snapshot.

        BybitClient already validates pagination/response shape, but this
        second boundary deliberately validates the lifecycle evidence before
        any registry mutation. It also protects custom/test clients.
        """
        if not isinstance(rows, (list, tuple)):
            raise UniverseSnapshotError(
                f"{expected_status} instrument snapshot "
                "must be a list or tuple"
            )

        result = {}

        for row in rows:
            if not isinstance(row, dict):
                raise UniverseSnapshotError(
                    f"{expected_status} snapshot contains "
                    "a non-object instrument"
                )

            symbol = row.get("symbol")

            if not isinstance(symbol, str) or not symbol.strip():
                raise UniverseSnapshotError(
                    f"{expected_status} snapshot contains "
                    "an invalid symbol"
                )

            symbol = symbol.strip()

            status = row.get("status")

            if status != expected_status:
                raise UniverseSnapshotError(
                    f"{symbol} appeared in {expected_status} "
                    f"snapshot with status {status!r}"
                )

            if symbol in result:
                raise UniverseSnapshotError(
                    f"duplicate instrument in "
                    f"{expected_status} snapshot: {symbol}"
                )

            result[symbol] = dict(row)

        return result

    @staticmethod
    def _terminal_time(row):
        """
        Return an authoritative terminal timestamp when Bybit supplies one.

        Perpetual instruments use deliveryTime as their delisting boundary.
        Keep delistTime as a compatibility fallback for existing metadata.
        """
        raw = row.get("deliveryTime")

        if raw in (None, "", 0, "0"):
            raw = row.get("delistTime")

        if raw in (None, "", 0, "0"):
            return None

        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise UniverseSnapshotError(
                f"invalid terminal timestamp for "
                f"{row.get('symbol')!r}"
            )

        if value <= 0:
            raise UniverseSnapshotError(
                f"invalid terminal timestamp for "
                f"{row.get('symbol')!r}"
            )

        return value

    def _validate_mass_disappearance(
        self,
        *,
        active,
        trading,
        explicitly_observed,
    ):
        """
        Guard only UNEXPLAINED disappearance.

        A known ACTIVE symbol moving to Delivering or Closed is accounted for
        by explicit exchange evidence and must not be mistaken for a damaged
        Trading snapshot.
        """
        if not active:
            return

        observed_any = set(trading).union(
            explicitly_observed
        )

        if not observed_any:
            raise UniverseSnapshotError(
                "exchange returned no lifecycle evidence for "
                "the existing active universe; refusing mass delist"
            )

        accounted = active.intersection(observed_any)
        accounted_ratio = len(accounted) / len(active)

        if accounted_ratio < self.minimum_snapshot_ratio:
            raise UniverseSnapshotError(
                "exchange lifecycle snapshot shrank suspiciously: "
                f"{len(active)} active -> "
                f"{len(accounted)} accounted; "
                "refusing mass delist"
            )

        missing = active - observed_any
        missing_ratio = len(missing) / len(active)

        # Percentage alone is unsafe for a small universe.
        # Treat this as mass disappearance only if both count and
        # percentage are significant.
        if (
            len(missing) >= self.minimum_mass_missing
            and missing_ratio > self.maximum_missing_ratio
        ):
            raise UniverseSnapshotError(
                "exchange lifecycle snapshot lost too many "
                "previously active symbols without explicit status: "
                f"{len(missing)} of {len(active)} "
                f"({missing_ratio:.1%}); "
                "refusing mass delist"
            )

    def _sync_legacy(self, observed_at):
        """
        Compatibility path for simple clients exposing only
        fetch_linear_symbols().

        This preserves the previously tested ACTIVE/MISSING fallback logic.
        """
        symbols = set(
            self.client.fetch_linear_symbols()
        )

        active = set(
            self.registry.active_symbols()
        )

        self._validate_mass_disappearance(
            active=active,
            trading=symbols,
            explicitly_observed=set(),
        )

        self.registry.reconcile(
            symbols,
            observed_at,
        )

        return symbols

    def _sync_explicit(self, observed_at):
        """
        Fetch ALL lifecycle datasets completely before touching SQLite.

        Any exception, malformed page, pagination failure or contradictory
        status snapshot therefore leaves the registry unchanged.
        """
        status_names = (
            "Trading",
            "PendingOpen",
            "PreLaunch",
            "Delivering",
            "Closed",
        )

        snapshots = {}

        # Network phase: absolutely no registry mutation here.
        for status in status_names:
            rows = self.client.fetch_linear_instruments(
                status=status
            )

            snapshots[status] = self._rows_by_symbol(
                rows,
                status,
            )

        # Detect exchange-race / contradictory snapshot.
        owner = {}

        for status in status_names:
            for symbol in snapshots[status]:
                previous = owner.get(symbol)

                if previous is not None:
                    raise UniverseSnapshotError(
                        f"instrument {symbol} appeared in "
                        f"multiple status snapshots: "
                        f"{previous}, {status}"
                    )

                owner[symbol] = status

        trading = set(
            snapshots["Trading"]
        )

        active = set(
            self.registry.active_symbols()
        )

        explicit_statuses = {}
        terminal_times = {}

        # PreLaunch is known to the exchange but has never become eligible.
        for symbol in snapshots["PreLaunch"]:
            explicit_statuses[symbol] = (
                InstrumentStatus.PRE_LISTING
            )

        # PendingOpen is pre-listing for a never-traded symbol, but a
        # previously known/traded symbol must be treated conservatively as
        # temporarily non-active rather than opening a new trading interval.
        for symbol in snapshots["PendingOpen"]:
            rec = self.registry.get(symbol)

            if (
                rec is None
                or rec.status is InstrumentStatus.PRE_LISTING
            ):
                explicit_statuses[symbol] = (
                    InstrumentStatus.PRE_LISTING
                )
            else:
                explicit_statuses[symbol] = (
                    InstrumentStatus.SUSPENDED
                )

        # Delivering is explicit exchange evidence that normal active
        # lifecycle has ended/paused, but it is not yet terminal history.
        for symbol in snapshots["Delivering"]:
            explicit_statuses[symbol] = (
                InstrumentStatus.SUSPENDED
            )

        # Closed is authoritative terminal evidence.
        #
        # Registry itself deliberately ignores unknown historical Closed
        # instruments, preventing a fresh install from importing the entire
        # historical Bybit catalogue.
        for symbol, row in snapshots["Closed"].items():
            explicit_statuses[symbol] = (
                InstrumentStatus.DELISTED
            )

            terminal_at = self._terminal_time(row)

            if terminal_at is not None:
                terminal_times[symbol] = terminal_at

        explicitly_observed = set(
            explicit_statuses
        )

        self._validate_mass_disappearance(
            active=active,
            trading=trading,
            explicitly_observed=explicitly_observed,
        )

        # SQLite mutation happens only now, after every status query and
        # every cross-snapshot validation has succeeded.
        self.registry.reconcile_lifecycle(
            trading,
            explicit_statuses,
            terminal_times,
            observed_at,
        )

        return trading

    def sync(self, observed_at: int):
        observed_at = int(observed_at)

        # Full BybitClient path.
        if hasattr(
            self.client,
            "fetch_linear_instruments",
        ):
            return self._sync_explicit(
                observed_at,
            )

        # Compatibility for existing/custom clients.
        return self._sync_legacy(
            observed_at,
        )
