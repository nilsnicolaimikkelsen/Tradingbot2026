from risk.gatekeeper import ApprovedOrder, RiskGatekeeper, RiskLimits, TradeIntent
from risk.kill_switch import KillSwitch


def _gatekeeper(**limit_overrides):
    limits = RiskLimits(**limit_overrides)
    return RiskGatekeeper(limits, KillSwitch())


def test_approves_and_sizes_order_within_limits():
    gatekeeper = _gatekeeper(max_position_risk_pct=0.01)
    intent = TradeIntent(symbol="BTC/USDT", side="buy", price=100.0, stop_distance=50.0)

    order = gatekeeper.evaluate(intent, capital=10_000, current_equity=10_000)

    assert order == ApprovedOrder(symbol="BTC/USDT", side="buy", size=2.0)


def test_blocks_when_kill_switch_already_triggered():
    kill_switch = KillSwitch()
    kill_switch.trigger("manual stop")
    gatekeeper = RiskGatekeeper(RiskLimits(), kill_switch)
    intent = TradeIntent(symbol="BTC/USDT", side="buy", price=100.0, stop_distance=50.0)

    order = gatekeeper.evaluate(intent, capital=10_000, current_equity=10_000)

    assert order is None


def test_daily_loss_limit_triggers_kill_switch_and_blocks():
    gatekeeper = _gatekeeper(max_daily_loss_pct=0.03)
    gatekeeper.start_of_day(equity=10_000)
    intent = TradeIntent(symbol="BTC/USDT", side="buy", price=100.0, stop_distance=50.0)

    order = gatekeeper.evaluate(intent, capital=9_600, current_equity=9_600)

    assert order is None
    assert gatekeeper.kill_switch.is_triggered is True
    assert gatekeeper.kill_switch.reason == "daily loss limit breached"


def test_weekly_loss_limit_triggers_kill_switch_and_blocks():
    gatekeeper = _gatekeeper(max_daily_loss_pct=0.5, max_weekly_loss_pct=0.08)
    gatekeeper.start_of_week(equity=10_000)
    intent = TradeIntent(symbol="BTC/USDT", side="buy", price=100.0, stop_distance=50.0)

    order = gatekeeper.evaluate(intent, capital=9_100, current_equity=9_100)

    assert order is None
    assert gatekeeper.kill_switch.is_triggered is True
    assert gatekeeper.kill_switch.reason == "weekly loss limit breached"


def test_no_order_when_stop_distance_zero():
    gatekeeper = _gatekeeper()
    intent = TradeIntent(symbol="BTC/USDT", side="buy", price=100.0, stop_distance=0.0)

    order = gatekeeper.evaluate(intent, capital=10_000, current_equity=10_000)

    assert order is None
