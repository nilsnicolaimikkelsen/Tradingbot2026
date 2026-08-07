"""Long-running orchestration process: fetch data, run strategy + risk, simulate paper fills.

Runs against Alpha Vantage FX_DAILY data and our own local fill simulator
(execution/backtest.py + execution/portfolio.py) — no broker account, no real orders.

Known gap: portfolio/position state is in-memory only and resets on restart.
CLAUDE.md calls for state persistence to the database; that's a follow-up, not yet built.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from data.alpha_vantage import AlphaVantageClient, AlphaVantageError
from data.service import sync_candles
from data.storage import CandleStore
from execution.backtest import BacktestExecutor
from execution.portfolio import Portfolio
from risk.gatekeeper import ApprovedOrder, RiskGatekeeper, RiskLimits, TradeIntent
from risk.kill_switch import KillSwitch
from strategy.indicators import average_true_range
from strategy.trend_following import TrendFollowingStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("trading_bot")

CHECK_INTERVAL_SECONDS = 6 * 60 * 60  # FX_DAILY updates once/day; a few checks/day is enough


class DailyRiskWindow:
    """Resets the gatekeeper's daily/weekly loss-limit baseline as calendar days/weeks roll over."""

    def __init__(self, gatekeeper: RiskGatekeeper):
        self._gatekeeper = gatekeeper
        self._last_day = None
        self._last_week = None

    def roll(self, equity: float) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self._last_day:
            self._gatekeeper.start_of_day(equity)
            self._last_day = today
        week = today.isocalendar()[:2]
        if week != self._last_week:
            self._gatekeeper.start_of_week(equity)
            self._last_week = week


async def run_once(
    client: AlphaVantageClient,
    store: CandleStore,
    strategy: TrendFollowingStrategy,
    gatekeeper: RiskGatekeeper,
    risk_window: DailyRiskWindow,
    executor: BacktestExecutor,
    portfolio: Portfolio,
    instrument: str,
    in_position: bool,
) -> bool:
    await sync_candles(client, store, instrument, granularity="daily", count=100)

    now = datetime.now(timezone.utc)
    candles = await store.get_candles(instrument, "daily", now - timedelta(days=200), now)
    if len(candles) < strategy.slow_window:
        logger.info("Ikke nok historikk ennaa (%d candles)", len(candles))
        return in_position

    signals = strategy.generate_signals(candles)
    volatility = average_true_range(candles)
    last = candles[-1]
    equity = portfolio.equity(last.close)
    risk_window.roll(equity)

    if signals.entries[-1] and not in_position and volatility[-1]:
        intent = TradeIntent(symbol=instrument, side="buy", price=last.close, stop_distance=volatility[-1])
        order = gatekeeper.evaluate(intent, capital=equity, current_equity=equity)
        if order is not None:
            fill = await executor.execute(order, last.close)
            portfolio.apply_fill(fill, last.close)
            logger.info("KJOPT %s %.4f @ %.5f", instrument, fill.size, fill.price)
            return True
    elif signals.exits[-1] and in_position and portfolio.position > 0:
        order = ApprovedOrder(symbol=instrument, side="sell", size=portfolio.position)
        fill = await executor.execute(order, last.close)
        portfolio.apply_fill(fill, last.close)
        logger.info("SOLGT %s %.4f @ %.5f", instrument, fill.size, fill.price)
        return False

    logger.info("Ingen signal. Egenkapital: %.2f", equity)
    return in_position


async def main() -> None:
    load_dotenv()

    client = AlphaVantageClient(api_key=os.environ["ALPHA_VANTAGE_API_KEY"])
    store = CandleStore(os.environ["DATABASE_URL"])
    await store.connect()

    instrument = os.environ.get("INSTRUMENT", "EUR_USD")
    strategy = TrendFollowingStrategy(fast_window=20, slow_window=50)
    kill_switch = KillSwitch()
    gatekeeper = RiskGatekeeper(RiskLimits(), kill_switch)
    risk_window = DailyRiskWindow(gatekeeper)
    executor = BacktestExecutor()
    portfolio = Portfolio(starting_cash=10_000.0)
    in_position = False

    logger.info("Trading-bot startet (paper trading, instrument=%s)", instrument)

    try:
        while True:
            if kill_switch.is_triggered:
                logger.warning("Kill switch aktivert (%s) - stopper handel.", kill_switch.reason)
                break
            try:
                in_position = await run_once(
                    client, store, strategy, gatekeeper, risk_window, executor, portfolio, instrument, in_position
                )
            except AlphaVantageError as e:
                logger.warning("Alpha Vantage-feil, proever igjen neste runde: %s", e)
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
    finally:
        await client.close()
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
