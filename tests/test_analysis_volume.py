"""Tests for volume analysis."""

from datetime import date, timedelta

from haoinvest.analysis.volume import analyze_volume
from haoinvest.db import Database
from haoinvest.models import MarketType, PriceBar


def _seed_volume_data(
    db: Database,
    symbol: str = "VOL",
    days: int = 30,
    base_volume: float = 1_000_000.0,
    last_day_multiplier: float = 1.0,
) -> None:
    """Seed price bars with controlled volume on the last day."""
    base_date = date(2025, 1, 1)
    bars = []
    for i in range(days):
        vol = base_volume if i < days - 1 else base_volume * last_day_multiplier
        bars.append(
            PriceBar(
                symbol=symbol,
                market_type=MarketType.A_SHARE,
                trade_date=base_date + timedelta(days=i),
                close=100.0,
                volume=vol,
            )
        )
    db.save_prices(bars)


class TestVolumeAnalysis:
    def test_normal_volume(self, db):
        """Volume near average should be 正常."""
        _seed_volume_data(db, last_day_multiplier=1.0)
        result = analyze_volume(db, "VOL", MarketType.A_SHARE)
        assert result.assessment == "正常"
        assert not result.is_anomaly
        assert result.volume_ratio is not None
        assert 0.8 <= result.volume_ratio <= 1.2

    def test_high_volume_anomaly(self, db):
        """Volume 3x average should flag as 放量 and is_anomaly=True."""
        _seed_volume_data(db, last_day_multiplier=3.0)
        result = analyze_volume(db, "VOL", MarketType.A_SHARE)
        assert result.assessment == "放量"
        assert result.is_anomaly is True
        assert result.volume_ratio is not None
        assert result.volume_ratio > 2.0

    def test_low_volume(self, db):
        """Volume 0.3x average should be 缩量."""
        _seed_volume_data(db, last_day_multiplier=0.3)
        result = analyze_volume(db, "VOL", MarketType.A_SHARE)
        assert result.assessment == "缩量"
        assert not result.is_anomaly

    def test_insufficient_data(self, db):
        """Should return message when not enough volume data."""
        _seed_volume_data(db, days=1)
        result = analyze_volume(db, "VOL", MarketType.A_SHARE)
        assert result.message is not None

    def test_verbose_explanation(self, db):
        """verbose=True should populate explanation."""
        _seed_volume_data(db, last_day_multiplier=2.5)
        result = analyze_volume(db, "VOL", MarketType.A_SHARE, verbose=True)
        assert result.explanation is not None
        assert "放量" in result.explanation
