"""Volume analysis: anomaly detection, turnover ratio."""

from datetime import date

from ..db import Database
from ..models import MarketType, VolumeAnalysis


def analyze_volume(
    db: Database,
    symbol: str,
    market_type: MarketType,
    start_date: date | None = None,
    end_date: date | None = None,
    verbose: bool = False,
) -> VolumeAnalysis:
    """Analyze volume patterns relative to 20-day average.

    Volume ratio > 2.0 flags as anomaly (放量).
    Volume ratio < 0.5 flags as 缩量.
    """
    bars = db.get_prices(symbol, market_type, start_date, end_date)
    mt_str = market_type.value if isinstance(market_type, MarketType) else market_type

    volumes = [b.volume for b in bars if b.volume is not None and b.volume > 0]

    if len(volumes) < 2:
        return VolumeAnalysis(
            symbol=symbol,
            market_type=mt_str,
            message=f"Not enough volume data ({len(volumes)} days)",
        )

    latest_volume = volumes[-1]

    # Use up to 20 days for average, excluding the latest day
    lookback = volumes[-21:-1] if len(volumes) > 21 else volumes[:-1]
    avg_volume_20d = sum(lookback) / len(lookback)

    if avg_volume_20d < 1e-10:
        return VolumeAnalysis(
            symbol=symbol,
            market_type=mt_str,
            latest_volume=latest_volume,
            message="Average volume is zero",
        )

    volume_ratio = latest_volume / avg_volume_20d
    is_anomaly = volume_ratio > 2.0

    if volume_ratio > 2.0:
        assessment = "放量"
    elif volume_ratio < 0.5:
        assessment = "缩量"
    else:
        assessment = "正常"

    explanation = None
    if verbose:
        explanation = (
            f"当日成交量是20日均量的{volume_ratio:.1f}倍，属于{assessment}状态"
        )
        if is_anomaly:
            explanation += "，需关注是否有重大消息或资金异动"
        elif assessment == "缩量":
            explanation += "，市场交投清淡，观望情绪较重"

    return VolumeAnalysis(
        symbol=symbol,
        market_type=mt_str,
        latest_volume=round(latest_volume, 2),
        avg_volume_20d=round(avg_volume_20d, 2),
        volume_ratio=round(volume_ratio, 2),
        is_anomaly=is_anomaly,
        assessment=assessment,
        explanation=explanation,
    )
