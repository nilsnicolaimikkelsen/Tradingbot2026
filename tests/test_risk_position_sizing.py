from risk.position_sizing import volatility_adjusted_size


def test_sizes_proportional_to_risk_amount():
    size = volatility_adjusted_size(capital=10_000, risk_pct=0.01, stop_distance=50)

    assert size == 2.0


def test_zero_size_when_stop_distance_is_zero():
    assert volatility_adjusted_size(capital=10_000, risk_pct=0.01, stop_distance=0) == 0.0


def test_zero_size_when_capital_is_zero():
    assert volatility_adjusted_size(capital=0, risk_pct=0.01, stop_distance=50) == 0.0
