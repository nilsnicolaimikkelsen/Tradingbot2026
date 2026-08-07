"""Independent kill switch that can halt all trading regardless of what the strategy wants."""


class KillSwitch:
    def __init__(self):
        self._triggered = False
        self._reason = ""

    def trigger(self, reason: str = "") -> None:
        self._triggered = True
        self._reason = reason

    def reset(self) -> None:
        self._triggered = False
        self._reason = ""

    @property
    def is_triggered(self) -> bool:
        return self._triggered

    @property
    def reason(self) -> str:
        return self._reason
