from risk.kill_switch import KillSwitch


def test_starts_not_triggered():
    switch = KillSwitch()

    assert switch.is_triggered is False


def test_trigger_and_reset():
    switch = KillSwitch()

    switch.trigger("manual stop")

    assert switch.is_triggered is True
    assert switch.reason == "manual stop"

    switch.reset()

    assert switch.is_triggered is False
    assert switch.reason == ""
