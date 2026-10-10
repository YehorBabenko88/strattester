class MarketDataError(RuntimeError):
    """Base class for market-data acquisition failures."""


class DatasetUnavailableError(MarketDataError):
    """
    The requested dataset is genuinely unavailable for the
    instrument/range/provider and retrying the same request is
    not expected to repair it.
    """


class MarketDataAccessError(MarketDataError):
    """
    Provider access is blocked or denied. The requirement is
    degraded rather than treated as missing market history.
    """


class RetryableMarketDataError(MarketDataError):
    """
    Temporary acquisition failure for which a later retry may
    succeed.
    """


class MarketDataIntegrityError(MarketDataError):
    """
    Provider returned malformed/inconsistent data. Never convert
    this into UNAVAILABLE merely because its message contains a
    particular phrase.
    """
