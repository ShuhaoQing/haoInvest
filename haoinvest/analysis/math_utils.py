"""Pure math helpers for technical analysis — no I/O or DB dependency."""

import math


def sma(values: list[float], period: int) -> float | None:
    """Simple moving average of the last *period* values."""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values: list[float], period: int) -> float | None:
    """Exponential moving average. Seeds with SMA then applies alpha smoothing."""
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1)
    ema_val = sum(values[:period]) / period
    for v in values[period:]:
        ema_val = alpha * v + (1 - alpha) * ema_val
    return ema_val


def _ema_series(values: list[float], period: int) -> list[float]:
    """Full EMA series used internally by compute_macd for signal line."""
    if len(values) < period:
        return []
    alpha = 2.0 / (period + 1)
    result: list[float] = []
    ema_val = sum(values[:period]) / period
    result.append(ema_val)
    for v in values[period:]:
        ema_val = alpha * v + (1 - alpha) * ema_val
        result.append(ema_val)
    return result


def compute_macd(
    closes: list[float],
) -> tuple[float | None, float | None, float | None]:
    """MACD = EMA(12) - EMA(26), signal = EMA(9) of MACD line."""
    if len(closes) < 26:
        return None, None, None

    ema12_series = _ema_series(closes, 12)
    ema26_series = _ema_series(closes, 26)

    offset = 26 - 12  # = 14
    macd_series = [
        ema12_series[offset + i] - ema26_series[i] for i in range(len(ema26_series))
    ]

    if len(macd_series) < 9:
        macd_line = macd_series[-1] if macd_series else None
        return macd_line, None, None

    signal_series = _ema_series(macd_series, 9)
    macd_line = macd_series[-1]
    signal_line = signal_series[-1]
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_rsi(closes: list[float], period: int = 14) -> float | None:
    """RSI = 100 - 100 / (1 + avg_gain / avg_loss). Uses smoothed averages."""
    if len(closes) < period + 1:
        return None

    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(c, 0) for c in changes]
    losses = [max(-c, 0) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss < 1e-10:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def compute_bollinger(
    closes: list[float], period: int = 20, num_std: float = 2.0
) -> tuple[float | None, float | None, float | None]:
    """Returns (upper, middle, lower). Middle = SMA, bands = ±num_std * std."""
    if len(closes) < period:
        return None, None, None

    window = closes[-period:]
    middle = sum(window) / period
    variance = sum((x - middle) ** 2 for x in window) / period
    std = math.sqrt(variance)
    upper = middle + num_std * std
    lower = middle - num_std * std
    return upper, middle, lower
