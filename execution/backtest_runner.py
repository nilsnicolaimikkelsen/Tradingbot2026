"""Ties data, strategy, risk, and (backtest) execution together for a single backtest run."""

from data.models import Candle
from execution.backtest import BacktestExecutor
from execution.portfolio import Portfolio, PortfolioMetrics
from risk.gatekeeper import ApprovedOrder, RiskGatekeeper, TradeIntent
from strategy.base import Strategy
from strategy.indicators import average_true_range


async def run_backtest(
    strategy: Strategy,
    gatekeeper: RiskGatekeeper,
    candles: list[Candle],
    starting_cash: float = 10_000.0,
    fee_pct: float = 0.001,
    slippage_pct: float = 0.0005,
    atr_window: int = 14,
) -> PortfolioMetrics:
    signals = strategy.generate_signals(candles)
    volatility = average_true_range(candles, window=atr_window)
    executor = BacktestExecutor(fee_pct=fee_pct, slippage_pct=slippage_pct)
    portfolio = Portfolio(starting_cash)
    in_position = False

    for i, candle in enumerate(candles):
        vol = volatility[i]
        equity = portfolio.equity(candle.close)

        if signals.entries[i] and not in_position and vol:
            intent = TradeIntent(symbol=candle.symbol, side="buy", price=candle.close, stop_distance=vol)
            order = gatekeeper.evaluate(intent, capital=equity, current_equity=equity)
            if order is not None:
                fill = await executor.execute(order, candle.close)
                portfolio.apply_fill(fill, candle.close)
                in_position = True
            else:
                portfolio.equity_curve.append(equity)
        elif signals.exits[i] and in_position and portfolio.position > 0:
            # Exits close the full existing position rather than going through the
            # gatekeeper's risk-based sizing, which only applies to new entries.
            order = ApprovedOrder(symbol=candle.symbol, side="sell", size=portfolio.position)
            fill = await executor.execute(order, candle.close)
            portfolio.apply_fill(fill, candle.close)
            in_position = False
        else:
            portfolio.equity_curve.append(equity)

    return portfolio.metrics()
