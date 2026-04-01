"""Technical indicators: MA, EMA, MACD, RSI, Bollinger Bands."""

from datetime import date

from ..db import Database
from ..models import (
    BollingerBands,
    MACDResult,
    MarketType,
    MovingAverages,
    RSIResult,
    TechnicalIndicators,
)
from .math_utils import compute_bollinger, compute_macd, compute_rsi, ema, sma


def analyze_technical(
    db: Database,
    symbol: str,
    market_type: MarketType,
    start_date: date | None = None,
    end_date: date | None = None,
    verbose: bool = False,
) -> TechnicalIndicators:
    """Calculate all technical indicators for a stock from cached price history.

    When verbose=True, each sub-result includes a Chinese explanation
    of what the indicator value means for a beginner investor.
    """
    bars = db.get_prices(symbol, market_type, start_date, end_date)
    closes = [b.close for b in bars if b.close is not None]

    mt_str = market_type.value

    if len(closes) < 14:
        return TechnicalIndicators(
            symbol=symbol,
            market_type=mt_str,
            message=f"Not enough price data ({len(closes)} days, need at least 14)",
        )

    latest_close = closes[-1]
    latest_date = bars[-1].trade_date if bars else None

    # --- Moving Averages ---
    sma_5 = sma(closes, 5)
    sma_10 = sma(closes, 10)
    sma_20 = sma(closes, 20)
    sma_60 = sma(closes, 60)
    ema_12 = ema(closes, 12)
    ema_26 = ema(closes, 26)

    # Trend assessment based on MA alignment
    above_count = sum(
        1 for ma in [sma_5, sma_10, sma_20] if ma is not None and latest_close > ma
    )
    available_mas = sum(1 for ma in [sma_5, sma_10, sma_20] if ma is not None)
    if available_mas == 0:
        trend = "无法判断"
    elif above_count == available_mas:
        trend = "上升趋势"
    elif above_count == 0:
        trend = "下降趋势"
    else:
        trend = "震荡"

    ma_explanation = None
    if verbose:
        ma_names = []
        for name, val in [("5日", sma_5), ("10日", sma_10), ("20日", sma_20)]:
            if val is not None:
                rel = "之上" if latest_close > val else "之下"
                ma_names.append(f"{name}均线{rel}")
        if ma_names:
            ma_explanation = f"收盘价在{'、'.join(ma_names)}，趋势判断为{trend}"

    ma = MovingAverages(
        sma_5=round(sma_5, 4) if sma_5 else None,
        sma_10=round(sma_10, 4) if sma_10 else None,
        sma_20=round(sma_20, 4) if sma_20 else None,
        sma_60=round(sma_60, 4) if sma_60 else None,
        ema_12=round(ema_12, 4) if ema_12 else None,
        ema_26=round(ema_26, 4) if ema_26 else None,
        trend=trend,
        explanation=ma_explanation,
    )

    # --- MACD ---
    macd_line, signal_line, histogram = compute_macd(closes)
    # Signal detection uses histogram sign (MACD line above/below signal line) as a
    # proxy for momentum direction. This differs from the traditional crossover event
    # (the moment MACD crosses the signal line). Histogram sign is simpler and works
    # well for trend confirmation; it does not pinpoint the exact crossover bar.
    if histogram is not None:
        if histogram > 0:
            macd_signal = "金叉"
        elif histogram < 0:
            macd_signal = "死叉"
        else:
            macd_signal = "无信号"
    else:
        macd_signal = "无信号"

    macd_explanation = None
    if verbose and histogram is not None:
        if macd_signal == "金叉":
            macd_explanation = "MACD柱为正（金叉），短期动能偏多，可能是买入信号"
        elif macd_signal == "死叉":
            macd_explanation = "MACD柱为负（死叉），短期动能偏空，可能是卖出信号"

    macd = MACDResult(
        macd_line=round(macd_line, 4) if macd_line is not None else None,
        signal_line=round(signal_line, 4) if signal_line is not None else None,
        histogram=round(histogram, 4) if histogram is not None else None,
        signal=macd_signal,
        explanation=macd_explanation,
    )

    # --- RSI ---
    rsi_val = compute_rsi(closes)
    if rsi_val is not None:
        if rsi_val > 70:
            rsi_assessment = "超买"
        elif rsi_val < 30:
            rsi_assessment = "超卖"
        else:
            rsi_assessment = "中性"
    else:
        rsi_assessment = "无法判断"

    rsi_explanation = None
    if verbose and rsi_val is not None:
        if rsi_assessment == "超买":
            rsi_explanation = f"RSI为{rsi_val:.1f}，超过70，股价可能超买，注意回调风险"
        elif rsi_assessment == "超卖":
            rsi_explanation = f"RSI为{rsi_val:.1f}，低于30，股价可能超卖，关注反弹机会"
        else:
            rsi_explanation = (
                f"RSI为{rsi_val:.1f}，处于30-70中性区间，无明显超买超卖信号"
            )

    rsi = RSIResult(
        rsi=round(rsi_val, 2) if rsi_val is not None else None,
        period=14,
        assessment=rsi_assessment,
        explanation=rsi_explanation,
    )

    # --- Bollinger Bands ---
    bb_upper, bb_middle, bb_lower = compute_bollinger(closes)
    if bb_upper is not None and bb_lower is not None and bb_middle is not None:
        bandwidth_pct = (bb_upper - bb_lower) / bb_middle * 100
        band_range = bb_upper - bb_lower
        if band_range > 0:
            relative_pos = (latest_close - bb_lower) / band_range
            # Thresholds 0.8/0.2 define "near upper/lower band" as the top/bottom 20%
            # of band width. This is a custom calibration: tight enough to signal
            # genuine proximity to the band without triggering on minor midline drift.
            if relative_pos > 0.8:
                bb_position = "上轨附近"
            elif relative_pos < 0.2:
                bb_position = "下轨附近"
            else:
                bb_position = "中轨附近"
        else:
            bb_position = "无法判断"
    else:
        bandwidth_pct = None
        bb_position = "无法判断"

    bb_explanation = None
    if verbose and bb_upper is not None:
        if bb_position == "上轨附近":
            bb_explanation = "价格接近布林带上轨，可能面临压力，注意回调风险"
        elif bb_position == "下轨附近":
            bb_explanation = "价格接近布林带下轨，可能存在支撑，关注反弹机会"
        else:
            bb_explanation = "价格在布林带中轨附近，波动正常"

    bollinger = BollingerBands(
        upper=round(bb_upper, 4) if bb_upper is not None else None,
        middle=round(bb_middle, 4) if bb_middle is not None else None,
        lower=round(bb_lower, 4) if bb_lower is not None else None,
        bandwidth_pct=round(bandwidth_pct, 2) if bandwidth_pct is not None else None,
        position=bb_position,
        explanation=bb_explanation,
    )

    # Warn when some indicators are unavailable due to insufficient data.
    # MACD needs 26+ days; Bollinger needs 20+ days.
    missing: list[str] = []
    if macd.macd_line is None:
        missing.append(f"MACD (需要 26 天，当前 {len(closes)} 天)")
    if bollinger.upper is None:
        missing.append(f"布林带 (需要 20 天，当前 {len(closes)} 天)")
    warning = f"部分指标不可用: {'; '.join(missing)}" if missing else None

    return TechnicalIndicators(
        symbol=symbol,
        market_type=mt_str,
        latest_close=latest_close,
        latest_date=latest_date,
        moving_averages=ma,
        macd=macd,
        rsi=rsi,
        bollinger=bollinger,
        message=warning,
    )
