"""Long-running orchestration process: fetch data, run strategy + risk, simulate paper fills.

Runs against Alpha Vantage FX_DAILY data and our own local fill simulator
(execution/backtest.py + execution/portfolio.py) — no broker account, no real orders.

Known gap: portfolio/position state is in-memory only and resets on restart.
CLAUDE.md calls for state persistence to the database; that's a follow-up, not yet built.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from data.alpha_vantage import AlphaVantageClient, AlphaVantageError
from data.service import sync_candles
from data.storage import CandleStore
from execution.backtest import BacktestExecutor
from execution.portfolio import Portfolio
from monitoring.github_status import GithubStatusPublisher
from risk.gatekeeper import ApprovedOrder, RiskGatekeeper, RiskLimits, TradeIntent
from risk.kill_switch import KillSwitch
from strategy.indicators import average_true_range
from strategy.trend_following import TrendFollowingStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("trading_bot")

# Alpha Vantage's free tier allows ~25 calls/day. Every check makes 1 call, so the
# default (2h -> 12 calls/day) leaves comfortable headroom. Override via
# CHECK_INTERVAL_SECONDS if you add more instruments or want a tighter/looser budget.
DEFAULT_CHECK_INTERVAL_SECONDS = 2 * 60 * 60
STATUS_REPO_OWNER = "nilsnicolaimikkelsen"
STATUS_REPO_NAME = "Tradingbot2026"


@dataclass
class RunResult:
    in_position: bool
    last_action: str  # "no_signal" | "bought" | "sold" | "blocked_by_risk" | "not_enough_history"


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
) -> RunResult:
    await sync_candles(client, store, instrument, granularity="daily", count=100)

    now = datetime.now(timezone.utc)
    candles = await store.get_candles(instrument, "daily", now - timedelta(days=200), now)
    if len(candles) < strategy.slow_window:
        logger.info("Ikke nok historikk ennaa (%d candles)", len(candles))
        return RunResult(in_position=in_position, last_action="not_enough_history")

    signals = strategy.generate_signals(candles)
    volatility = average_true_range(candles)
    last = candles[-1]
    equity = portfolio.equity(last.close)
    risk_window.roll(equity)

    last_action = "no_signal"
    traded = False

    if signals.entries[-1] and not in_position and volatility[-1]:
        intent = TradeIntent(symbol=instrument, side="buy", price=last.close, stop_distance=volatility[-1])
        order = gatekeeper.evaluate(intent, capital=equity, current_equity=equity)
        if order is not None:
            fill = await executor.execute(order, last.close)
            portfolio.apply_fill(fill, last.close)
            logger.info("KJOPT %s %.4f @ %.5f", instrument, fill.size, fill.price)
            in_position = True
            last_action = "bought"
            traded = True
        else:
            last_action = "blocked_by_risk"
    elif signals.exits[-1] and in_position and portfolio.position > 0:
        order = ApprovedOrder(symbol=instrument, side="sell", size=portfolio.position)
        fill = await executor.execute(order, last.close)
        portfolio.apply_fill(fill, last.close)
        logger.info("SOLGT %s %.4f @ %.5f", instrument, fill.size, fill.price)
        in_position = False
        last_action = "sold"
        traded = True

    if not traded:
        portfolio.equity_curve.append(equity)

    logger.info("Status: %s. Egenkapital: %.2f", last_action, portfolio.equity_curve[-1])
    return RunResult(in_position=in_position, last_action=last_action)


async def _publish_status(
    publisher: GithubStatusPublisher,
    instrument: str,
    in_position: bool,
    last_action: str,
    portfolio: Portfolio,
    kill_switch: KillSwitch,
    error: str | None,
) -> None:
    status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "instrument": instrument,
        "in_position": in_position,
        "last_action": last_action,
        "equity": portfolio.equity_curve[-1] if portfolio.equity_curve else portfolio.starting_cash,
        "kill_switch_triggered": kill_switch.is_triggered,
        "kill_switch_reason": kill_switch.reason,
        "error": error,
    }
    try:
        await publisher.publish(status)
    except Exception as e:  # a status-publish hiccup should never crash the bot
        logger.warning("Klarte ikke publisere status til GitHub: %s", e)


async def main() -> None:
    load_dotenv()

    client = AlphaVantageClient(api_key=os.environ["ALPHA_VANTAGE_API_KEY"])
    store = CandleStore(os.environ["DATABASE_URL"])
    await store.connect()

    instrument = os.environ.get("INSTRUMENT", "EUR_USD")
    check_interval_seconds = int(os.environ.get("CHECK_INTERVAL_SECONDS", DEFAULT_CHECK_INTERVAL_SECONDS))
    strategy = TrendFollowingStrategy(fast_window=20, slow_window=50)
    kill_switch = KillSwitch()
    gatekeeper = RiskGatekeeper(RiskLimits(), kill_switch)
    risk_window = DailyRiskWindow(gatekeeper)
    executor = BacktestExecutor()
    portfolio = Portfolio(starting_cash=10_000.0)
    in_position = False
    last_action = "startup"

    github_token = os.environ.get("GITHUB_TOKEN")
    status_publisher = (
        GithubStatusPublisher(token=github_token, owner=STATUS_REPO_OWNER, repo=STATUS_REPO_NAME)
        if github_token
        else None
    )

    logger.info("Trading-bot startet (paper trading, instrument=%s)", instrument)

    try:
        while True:
            if kill_switch.is_triggered:
                logger.warning("Kill switch aktivert (%s) - stopper handel.", kill_switch.reason)
                if status_publisher is not None:
                    await _publish_status(
                        status_publisher, instrument, in_position, "kill_switch", portfolio, kill_switch, error=None
                    )
                break

            error = None
            try:
                result = await run_once(
                    client, store, strategy, gatekeeper, risk_window, executor, portfolio, instrument, in_position
                )
                in_position = result.in_position
                last_action = result.last_action
            except AlphaVantageError as e:
                error = str(e)
                last_action = "error"
                logger.warning("Alpha Vantage-feil, proever igjen neste runde: %s", e)

            if status_publisher is not None:
                await _publish_status(
                    status_publisher, instrument, in_position, last_action, portfolio, kill_switch, error
                )

            await asyncio.sleep(check_interval_seconds)
    finally:
        await client.close()
        await store.close()
        if status_publisher is not None:
            await status_publisher.close()


if __name__ == "__main__":
    asyncio.run(main())
