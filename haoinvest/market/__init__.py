"""Market data providers with unified interface."""

from .provider import MarketProvider
from ..models import MarketType

_registry: dict[MarketType, type[MarketProvider]] = {}


def register_provider(
    market_type: MarketType, provider_cls: type[MarketProvider]
) -> None:
    _registry[market_type] = provider_cls


def get_provider(market_type: MarketType) -> MarketProvider:
    """Get a market data provider instance for the given market type."""
    if market_type not in _registry:
        raise ValueError(f"No provider registered for market type: {market_type.value}")
    return _registry[market_type]()


def _auto_register() -> None:
    """Register built-in providers."""
    try:
        from .akshare_provider import AKShareProvider

        register_provider(MarketType.A_SHARE, AKShareProvider)
    except ImportError:
        pass

    try:
        from .crypto_provider import CryptoProvider

        register_provider(MarketType.CRYPTO, CryptoProvider)
    except ImportError:
        pass

    try:
        from .us_provider import USProvider

        register_provider(MarketType.US, USProvider)
    except ImportError:
        pass


_auto_register()
