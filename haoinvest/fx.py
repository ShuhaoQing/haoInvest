"""Currency conversion utilities."""

import httpx

from .http_retry import api_retry

# Hardcoded fallback rates (updated manually when needed)
_FALLBACK_RATES = {
    ("USD", "CNY"): 7.25,
    ("CNY", "USD"): 1 / 7.25,
    ("USDT", "CNY"): 7.25,
    ("CNY", "USDT"): 1 / 7.25,
    ("HKD", "CNY"): 0.93,
    ("CNY", "HKD"): 1 / 0.93,
    ("USD", "USDT"): 1.0,
    ("USDT", "USD"): 1.0,
}


def convert(amount: float, from_ccy: str, to_ccy: str) -> float:
    """Convert amount between currencies.

    Uses a simple exchange rate lookup. For a personal portfolio tool,
    approximate rates are acceptable — precision to 2 decimal places.
    """
    from_ccy = from_ccy.upper()
    to_ccy = to_ccy.upper()

    if from_ccy == to_ccy:
        return amount

    rate = _get_rate(from_ccy, to_ccy)
    return round(amount * rate, 2)


def _get_rate(from_ccy: str, to_ccy: str) -> float:
    """Get exchange rate, trying live API first, falling back to hardcoded rates."""
    # Try live rate
    try:
        return _fetch_live_rate(from_ccy, to_ccy)
    except Exception:
        pass

    # Fallback to hardcoded
    key = (from_ccy, to_ccy)
    if key in _FALLBACK_RATES:
        return _FALLBACK_RATES[key]

    # Try triangulation through USD
    try:
        to_usd = _FALLBACK_RATES.get((from_ccy, "USD")) or (
            1.0 / _FALLBACK_RATES[("USD", from_ccy)]
        )
        from_usd = _FALLBACK_RATES.get(("USD", to_ccy)) or (
            1.0 / _FALLBACK_RATES[(to_ccy, "USD")]
        )
        return to_usd * from_usd
    except (KeyError, ZeroDivisionError):
        raise ValueError(f"No exchange rate available for {from_ccy} → {to_ccy}")


@api_retry
def _fetch_live_rate(from_ccy: str, to_ccy: str) -> float:
    """Fetch live rate from a free API. Raises on failure."""
    # exchangerate-api.com free tier
    resp = httpx.get(
        f"https://open.er-api.com/v6/latest/{from_ccy}",
        timeout=5.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("result") != "success":
        raise ValueError("API returned error")
    rates = data.get("rates", {})
    if to_ccy not in rates:
        raise ValueError(f"{to_ccy} not found in rates")
    return float(rates[to_ccy])
