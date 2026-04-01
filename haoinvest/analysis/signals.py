"""Signal aggregation: combines technical indicators into a directional signal."""

from datetime import date

from ..db import Database
from ..models import MarketType, SignalSummary
from .technical import analyze_technical
from .volume import analyze_volume


def aggregate_signals(
    db: Database,
    symbol: str,
    market_type: MarketType,
    start_date: date | None = None,
    end_date: date | None = None,
    verbose: bool = False,
) -> SignalSummary:
    """Combine technical indicators into a single directional signal.

    Counts bullish/bearish/neutral votes from:
    1. MA trend (price vs SMA20)
    2. MACD histogram sign
    3. RSI zone (overbought/oversold/neutral)
    4. Bollinger band position

    Volume anomaly amplifies trend description but does not vote.
    Confidence: 4 agree = 高, 3 = 中, else 低.
    """
    mt_str = market_type.value

    tech = analyze_technical(db, symbol, market_type, start_date, end_date)
    vol = analyze_volume(db, symbol, market_type, start_date, end_date)

    # If tech has a message (insufficient data or partial-data warning), skip all voting.
    # Even with partial data (14–25 days), where RSI/MA are available, we bail out
    # rather than vote on a subset — a partial vote could mislead users about signal strength.
    if tech.message:
        return SignalSummary(
            symbol=symbol,
            market_type=mt_str,
            explanation=tech.message if verbose else None,
        )

    bullish = 0
    bearish = 0
    neutral = 0
    details: list[str] = []

    # 1. MA trend
    if tech.moving_averages.trend == "上升趋势":
        bullish += 1
        details.append("均线: 多头排列 (+1 多)")
    elif tech.moving_averages.trend == "下降趋势":
        bearish += 1
        details.append("均线: 空头排列 (+1 空)")
    else:
        neutral += 1
        details.append("均线: 震荡 (中性)")

    # 2. MACD
    if tech.macd.signal == "金叉":
        bullish += 1
        details.append("MACD: 金叉 (+1 多)")
    elif tech.macd.signal == "死叉":
        bearish += 1
        details.append("MACD: 死叉 (+1 空)")
    else:
        neutral += 1
        details.append("MACD: 无信号 (中性)")

    # 3. RSI
    if tech.rsi.assessment == "超卖":
        bullish += 1
        details.append("RSI: 超卖区 (+1 多)")
    elif tech.rsi.assessment == "超买":
        bearish += 1
        details.append("RSI: 超买区 (+1 空)")
    else:
        neutral += 1
        details.append("RSI: 中性区间 (中性)")

    # 4. Bollinger
    if tech.bollinger.position == "下轨附近":
        bullish += 1
        details.append("布林带: 下轨附近 (+1 多)")
    elif tech.bollinger.position == "上轨附近":
        bearish += 1
        details.append("布林带: 上轨附近 (+1 空)")
    else:
        neutral += 1
        details.append("布林带: 中轨附近 (中性)")

    # Volume note (does not vote)
    if vol.is_anomaly:
        details.append(f"成交量: 放量 (ratio={vol.volume_ratio}x, 趋势确认)")
    elif vol.assessment == "缩量":
        details.append(f"成交量: 缩量 (ratio={vol.volume_ratio}x)")

    # Overall signal
    if bullish > bearish:
        overall = "偏多"
    elif bearish > bullish:
        overall = "偏空"
    else:
        overall = "中性"

    # Confidence
    max_votes = max(bullish, bearish, neutral)
    if max_votes >= 4:
        confidence = "高"
    elif max_votes >= 3:
        confidence = "中"
    else:
        confidence = "低"

    explanation = None
    if verbose:
        lines = [f"综合信号: {overall} (置信度: {confidence})"]
        lines.append(
            f"  多头指标: {bullish}个, 空头指标: {bearish}个, 中性: {neutral}个"
        )
        for d in details:
            lines.append(f"  - {d}")
        if overall == "偏多":
            lines.append(
                "  提示: 多数指标偏多，但技术分析仅供参考，需结合基本面和市场环境"
            )
        elif overall == "偏空":
            lines.append("  提示: 多数指标偏空，注意控制风险，避免盲目抄底")
        else:
            lines.append("  提示: 信号分歧较大，建议观望等待方向明确")
        explanation = "\n".join(lines)

    return SignalSummary(
        symbol=symbol,
        market_type=mt_str,
        overall_signal=overall,
        confidence=confidence,
        bullish_count=bullish,
        bearish_count=bearish,
        neutral_count=neutral,
        details=details,
        explanation=explanation,
    )
