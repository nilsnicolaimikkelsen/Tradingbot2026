"""Risk gatekeeper: sits between strategy and execution, can block or resize any trade."""

from dataclasses import dataclass

from risk.kill_switch import KillSwitch
from risk.position_sizing import volatility_adjusted_size


@dataclass(frozen=True)
class RiskLimits:
    max_position_risk_pct: float = 0.01
    max_daily_loss_pct: float = 0.03
    max_weekly_loss_pct: float = 0.08


@dataclass(frozen=True)
class TradeIntent:
    symbol: str
    side: str
    price: float
    stop_distance: float


@dataclass(frozen=True)
class ApprovedOrder:
    symbol: str
    side: str
    size: float


class RiskGatekeeper:
    def __init__(self, limits: RiskLimits, kill_switch: KillSwitch):
        self.limits = limits
        self.kill_switch = kill_switch
        self._equity_start_of_day: float | None = None
        self._equity_start_of_week: float | None = None

    def start_of_day(self, equity: float) -> None:
        self._equity_start_of_day = equity

    def start_of_week(self, equity: float) -> None:
        self._equity_start_of_week = equity

    def evaluate(self, intent: TradeIntent, capital: float, current_equity: float) -> ApprovedOrder | None:
        if self.kill_switch.is_triggered:
            return None

        if self._breaches_loss_limit(self._equity_start_of_day, current_equity, self.limits.max_daily_loss_pct):
            self.kill_switch.trigger("daily loss limit breached")
            return None

        if self._breaches_loss_limit(self._equity_start_of_week, current_equity, self.limits.max_weekly_loss_pct):
            self.kill_switch.trigger("weekly loss limit breached")
            return None

        size = volatility_adjusted_size(capital, self.limits.max_position_risk_pct, intent.stop_distance)
        if size <= 0:
            return None

        return ApprovedOrder(symbol=intent.symbol, side=intent.side, size=size)

    @staticmethod
    def _breaches_loss_limit(equity_start: float | None, current_equity: float, max_loss_pct: float) -> bool:
        if equity_start is None or equity_start <= 0:
            return False
        loss_pct = (equity_start - current_equity) / equity_start
        return loss_pct >= max_loss_pct
