from datetime import datetime, timezone

from data.models import parse_ohlcv_row


def test_parse_ohlcv_row():
    row = [1700000000000, 100.0, 110.0, 95.0, 105.0, 42.5]

    candle = parse_ohlcv_row("BTC/USDT", "1h", row)

    assert candle.symbol == "BTC/USDT"
    assert candle.timeframe == "1h"
    assert candle.timestamp == datetime.fromtimestamp(1700000000, tz=timezone.utc)
    assert candle.open == 100.0
    assert candle.high == 110.0
    assert candle.low == 95.0
    assert candle.close == 105.0
    assert candle.volume == 42.5
