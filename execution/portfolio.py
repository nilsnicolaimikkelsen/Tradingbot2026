"""Tracks cash/position/equity through a sequence of fills and computes performance metrics."""

from dataclasses import dataclass

from execution.base import Fill


@dataclass(frozen=True)
class PortfolioMetrics:
    total_return_pct: float
    max_drawdown_pct: float
    win_rate: float
    num_trades: int


class Portfolio:
    def __init__(self, starting_cash: float):
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.position = 0.0
        self._entry_price: float | None = None
        self._trade_pnls: list[float] = []
        self.equity_curve: list[float] = [starting_cash]

    def apply_fill(self, fill: Fill, mark_price: float) -> None:
        if fill.side == "buy":
            self.cash -= fill.price * fill.size + fill.fee
            self.position += fill.size
            self._entry_price = fill.price
        else:
            self.cash += fill.price * fill.size - fill.fee
            if self._entry_price is not None:
                self._trade_pnls.append((fill.price - self._entry_price) * fill.size - fill.fee)
            self.position -= fill.size
            if self.position <= 0:
                self._entry_price = None
        self.equity_curve.append(self.equity(mark_price))

    def equity(self, mark_price: float) -> float:
        return self.cash + self.position * mark_price

    def metrics(self) -> PortfolioMetrics:
        final_equity = self.equity_curve[-1]
        total_return_pct = (final_equity - self.starting_cash) / self.starting_cash

        peak = self.equity_curve[0]
        max_drawdown = 0.0
        for value in self.equity_curve:
            peak = max(peak, value)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - value) / peak)

        wins = sum(1 for pnl in self._trade_pnls if pnl > 0)
        win_rate = wins / len(self._trade_pnls) if self._trade_pnls else 0.0

        return PortfolioMetrics(
            total_return_pct=total_return_pct,
            max_drawdown_pct=max_drawdown,
            win_rate=win_rate,
            num_trades=len(self._trade_pnls),
        )
