"""Technical indicator computation using pandas-ta."""

import pandas as pd
import pandas_ta_classic  # noqa: F401 — registers df.ta accessor

from ..models import (
    BollingerBands,
    MACDResult,
    MovingAverages,
    RSIResult,
    TechnicalIndicators,
)
from .databridge import safe_float


def _assess_ma_trend(
    latest_close: float,
    sma_5: float | None,
    sma_10: float | None,
    sma_20: float | None,
    verbose: bool,
) -> tuple[str, str | None]:
    """Determine trend from MA alignment. Returns (trend_label, explanation_or_none)."""
    mas = [sma_5, sma_10, sma_20]
    available = [m for m in mas if m is not None]
    if not available:
        return "无法判断", None

    above_count = sum(1 for m in available if latest_close > m)
    if above_count == len(available):
        trend = "上升趋势"
    elif above_count == 0:
        trend = "下降趋势"
    else:
        trend = "震荡"

    explanation = None
    if verbose:
        parts = []
        for name, val in [("5日", sma_5), ("10日", sma_10), ("20日", sma_20)]:
            if val is not None:
                rel = "之上" if latest_close > val else "之下"
                parts.append(f"{name}均线{rel}")
        if parts:
            explanation = f"收盘价在{'、'.join(parts)}，趋势判断为{trend}"

    return trend, explanation


def _assess_macd(
    histogram: float | None,
    verbose: bool,
) -> tuple[str, str | None]:
    """Assess MACD signal from histogram. Returns (signal_label, explanation_or_none)."""
    if histogram is None:
        return "无信号", None

    if histogram > 0:
        signal = "金叉"
    elif histogram < 0:
        signal = "死叉"
    else:
        signal = "无信号"

    explanation = None
    if verbose:
        if signal == "金叉":
            explanation = "MACD柱为正（金叉），短期动能偏多，可能是买入信号"
        elif signal == "死叉":
            explanation = "MACD柱为负（死叉），短期动能偏空，可能是卖出信号"

    return signal, explanation


def _assess_rsi(
    rsi_val: float | None,
    verbose: bool,
) -> tuple[str, str | None]:
    """Assess RSI zone. Returns (assessment_label, explanation_or_none)."""
    if rsi_val is None:
        return "无法判断", None

    if rsi_val > 70:
        assessment = "超买"
    elif rsi_val < 30:
        assessment = "超卖"
    else:
        assessment = "中性"

    explanation = None
    if verbose:
        if assessment == "超买":
            explanation = f"RSI为{rsi_val:.1f}，超过70，股价可能超买，注意回调风险"
        elif assessment == "超卖":
            explanation = f"RSI为{rsi_val:.1f}，低于30，股价可能超卖，关注反弹机会"
        else:
            explanation = f"RSI为{rsi_val:.1f}，处于30-70中性区间，无明显超买超卖信号"

    return assessment, explanation


def _assess_bollinger(
    latest_close: float,
    upper: float | None,
    middle: float | None,
    lower: float | None,
    verbose: bool,
) -> tuple[float | None, str, str | None]:
    """Assess Bollinger position. Returns (bandwidth_pct, position, explanation)."""
    if upper is None or middle is None or lower is None:
        return None, "无法判断", None

    bandwidth_pct = (upper - lower) / middle * 100
    band_range = upper - lower
    if band_range > 0:
        relative_pos = (latest_close - lower) / band_range
        if relative_pos > 0.8:
            position = "上轨附近"
        elif relative_pos < 0.2:
            position = "下轨附近"
        else:
            position = "中轨附近"
    else:
        position = "无法判断"

    explanation = None
    if verbose and upper is not None:
        if position == "上轨附近":
            explanation = "价格接近布林带上轨，可能面临压力，注意回调风险"
        elif position == "下轨附近":
            explanation = "价格接近布林带下轨，可能存在支撑，关注反弹机会"
        else:
            explanation = "价格在布林带中轨附近，波动正常"

    return bandwidth_pct, position, explanation


def _r(val: float | None, ndigits: int = 4) -> float | None:
    """Round a value or return None."""
    return round(val, ndigits) if val is not None else None


def compute_technical(
    df: pd.DataFrame,
    verbose: bool = False,
) -> TechnicalIndicators:
    """Compute all technical indicators using pandas-ta.

    Expects an OHLCV DataFrame with DatetimeIndex (from databridge).
    Returns a TechnicalIndicators model. The symbol and market_type fields
    are left as empty strings — the adapter layer fills them in.
    """
    latest_close = float(df["close"].iloc[-1])
    latest_date = df.index[-1].date()

    # --- Moving Averages ---
    sma_5 = safe_float(df.ta.sma(length=5).iloc[-1]) if len(df) >= 5 else None
    sma_10 = safe_float(df.ta.sma(length=10).iloc[-1]) if len(df) >= 10 else None
    sma_20 = safe_float(df.ta.sma(length=20).iloc[-1]) if len(df) >= 20 else None
    sma_60 = safe_float(df.ta.sma(length=60).iloc[-1]) if len(df) >= 60 else None
    ema_12 = safe_float(df.ta.ema(length=12).iloc[-1]) if len(df) >= 12 else None
    ema_26 = safe_float(df.ta.ema(length=26).iloc[-1]) if len(df) >= 26 else None

    trend, ma_explanation = _assess_ma_trend(
        latest_close, sma_5, sma_10, sma_20, verbose
    )

    ma = MovingAverages(
        sma_5=_r(sma_5),
        sma_10=_r(sma_10),
        sma_20=_r(sma_20),
        sma_60=_r(sma_60),
        ema_12=_r(ema_12),
        ema_26=_r(ema_26),
        trend=trend,
        explanation=ma_explanation,
    )

    # --- MACD ---
    macd_line = None
    signal_line = None
    histogram = None
    if len(df) >= 26:
        macd_df = df.ta.macd(fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            macd_line = safe_float(macd_df.iloc[-1, 0])  # MACD_12_26_9
            histogram = safe_float(macd_df.iloc[-1, 1])  # MACDh_12_26_9
            signal_line = safe_float(macd_df.iloc[-1, 2])  # MACDs_12_26_9

    macd_signal, macd_explanation = _assess_macd(histogram, verbose)

    macd_result = MACDResult(
        macd_line=_r(macd_line),
        signal_line=_r(signal_line),
        histogram=_r(histogram),
        signal=macd_signal,
        explanation=macd_explanation,
    )

    # --- RSI ---
    rsi_val = None
    if len(df) >= 15:
        rsi_series = df.ta.rsi(length=14)
        if rsi_series is not None:
            rsi_val = safe_float(rsi_series.iloc[-1])

    rsi_assessment, rsi_explanation = _assess_rsi(rsi_val, verbose)

    rsi_result = RSIResult(
        rsi=_r(rsi_val, 2),
        period=14,
        assessment=rsi_assessment,
        explanation=rsi_explanation,
    )

    # --- Bollinger Bands ---
    bb_upper = None
    bb_middle = None
    bb_lower = None
    if len(df) >= 20:
        bb_df = df.ta.bbands(length=20, std=2)
        if bb_df is not None and not bb_df.empty:
            bb_lower = safe_float(bb_df.iloc[-1, 0])  # BBL_20_2.0
            bb_middle = safe_float(bb_df.iloc[-1, 1])  # BBM_20_2.0
            bb_upper = safe_float(bb_df.iloc[-1, 2])  # BBU_20_2.0

    bandwidth_pct, bb_position, bb_explanation = _assess_bollinger(
        latest_close, bb_upper, bb_middle, bb_lower, verbose
    )

    bollinger = BollingerBands(
        upper=_r(bb_upper),
        middle=_r(bb_middle),
        lower=_r(bb_lower),
        bandwidth_pct=_r(bandwidth_pct, 2),
        position=bb_position,
        explanation=bb_explanation,
    )

    # Warn when some indicators are unavailable
    missing: list[str] = []
    if macd_result.macd_line is None:
        missing.append(f"MACD (需要 26 天，当前 {len(df)} 天)")
    if bollinger.upper is None:
        missing.append(f"布林带 (需要 20 天，当前 {len(df)} 天)")
    warning = f"部分指标不可用: {'; '.join(missing)}" if missing else None

    return TechnicalIndicators(
        symbol="",
        market_type="",
        latest_close=latest_close,
        latest_date=latest_date,
        moving_averages=ma,
        macd=macd_result,
        rsi=rsi_result,
        bollinger=bollinger,
        message=warning,
    )
