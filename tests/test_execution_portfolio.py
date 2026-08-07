import pytest

from execution.base import Fill
from execution.portfolio import Portfolio


def test_winning_trade_tracks_equity_return_and_win_rate():
    portfolio = Portfolio(starting_cash=1000.0)

    portfolio.apply_fill(Fill(symbol="BTC/USDT", side="buy", size=1.0, price=100.0, fee=1.0), mark_price=100.0)
    portfolio.apply_fill(Fill(symbol="BTC/USDT", side="sell", size=1.0, price=110.0, fee=1.0), mark_price=110.0)

    metrics = portfolio.metrics()

    assert metrics.num_trades == 1
    assert metrics.win_rate == 1.0
    assert metrics.total_return_pct == pytest.approx(0.008)
    assert metrics.max_drawdown_pct == pytest.approx(0.001)


def test_losing_trade_tracked_as_loss():
    portfolio = Portfolio(starting_cash=1000.0)

    portfolio.apply_fill(Fill(symbol="BTC/USDT", side="buy", size=1.0, price=100.0, fee=0.0), mark_price=100.0)
    portfolio.apply_fill(Fill(symbol="BTC/USDT", side="sell", size=1.0, price=90.0, fee=0.0), mark_price=90.0)

    metrics = portfolio.metrics()

    assert metrics.win_rate == 0.0
    assert metrics.num_trades == 1
    assert metrics.total_return_pct == pytest.approx(-0.01)
