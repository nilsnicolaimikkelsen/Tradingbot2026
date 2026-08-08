"""Long-running orchestration process: fetch data, run strategy + risk, simulate paper fills.

Runs several (instrument, strategy) "lines" -- e.g. 8 pairs x 2 strategies -- each with
its own capital slice, so trade frequency comes from breadth (more pairs, uncorrelated
strategies) rather than from loosening any single strategy's entry quality bar.

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
from data.models import Candle
from data.service import sync_candles
from data.storage import CandleStore
from execution.backtest import BacktestExecutor
from execution.portfolio import Portfolio
from monitoring.github_status import GithubStatusPublisher
from risk.gatekeeper import ApprovedOrder, RiskGatekeeper, RiskLimits, TradeIntent
from risk.kill_switch import KillSwitch
from strategy.base import Strategy
from strategy.indicators import average_true_range
from strategy.mean_reversion import MeanReversionStrategy
from strategy.trend_following import TrendFollowingStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("trading_bot")

MIN_HISTORY_WARMUP = 60  # enough candles for the slowest indicator window (50-day trend)

# Alpha Vantage's free tier allows ~25 calls/day, and each check makes exactly one
# call per *instrument* regardless of how many strategies run against it (they
# share the same fetched candles). The default check interval scales with
# instrument count to land around TARGET_CALLS_PER_DAY total, leaving margin under
# the cap. Override CHECK_INTERVAL_SECONDS directly if you want something else.
DEFAULT_INSTRUMENTS = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF", "NZD_USD", "EUR_GBP"]
TARGET_CALLS_PER_DAY = 16
STATUS_REPO_OWNER = "nilsnicolaimikkelsen"
STATUS_REPO_NAME = "Tradingbot2026"


def strategy_factories() -> list[callable]:
    return [
        lambda: TrendFollowingStrategy(fast_window=20, slow_window=50),
        lambda: MeanReversionStrategy(),
    ]


@dataclass
class TradingLine:
    """One (instrument, strategy) pair, with its own capital slice and position state."""

    instrument: str
    strategy: Strategy
    gatekeeper: RiskGatekeeper
    risk_window: "DailyRiskWindow"
    portfolio: Portfolio
    in_position: bool = False

    @property
    def line_id(self) -> str:
        return f"{self.instrument}:{self.strategy.name}"


@dataclass
class RunResult:
    line_id: str
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


async def evaluate_line(executor: BacktestExecutor, line: TradingLine, candles: list[Candle]) -> RunResult:
    if len(candles) < MIN_HISTORY_WARMUP:
        logger.info("[%s] Ikke nok historikk ennaa (%d candles)", line.line_id, len(candles))
        return RunResult(line.line_id, line.in_position, "not_enough_history")

    signals = line.strategy.generate_signals(candles)
    volatility = average_true_range(candles)
    last = candles[-1]
    equity = line.portfolio.equity(last.close)
    line.risk_window.roll(equity)

    last_action = "no_signal"
    traded = False

    if signals.entries[-1] and not line.in_position and volatility[-1]:
        intent = TradeIntent(symbol=line.instrument, side="buy", price=last.close, stop_distance=volatility[-1])
        order = line.gatekeeper.evaluate(intent, capital=equity, current_equity=equity)
        if order is not None:
            fill = await executor.execute(order, last.close)
            line.portfolio.apply_fill(fill, last.close)
            logger.info("KJOPT [%s] %.4f @ %.5f", line.line_id, fill.size, fill.price)
            line.in_position = True
            last_action = "bought"
            traded = True
        else:
            last_action = "blocked_by_risk"
    elif signals.exits[-1] and line.in_position and line.portfolio.position > 0:
        order = ApprovedOrder(symbol=line.instrument, side="sell", size=line.portfolio.position)
        fill = await executor.execute(order, last.close)
        line.portfolio.apply_fill(fill, last.close)
        logger.info("SOLGT [%s] %.4f @ %.5f", line.line_id, fill.size, fill.price)
        line.in_position = False
        last_action = "sold"
        traded = True

    if not traded:
        line.portfolio.equity_curve.append(equity)

    logger.info("Status [%s]: %s. Egenkapital: %.2f", line.line_id, last_action, line.portfolio.equity_curve[-1])
    return RunResult(line.line_id, line.in_position, last_action)


async def check_all(
    client: AlphaVantageClient, store: CandleStore, executor: BacktestExecutor, lines: list[TradingLine]
) -> tuple[list[RunResult], list[str]]:
    """Evaluates every line, grouped by instrument so each is fetched once.

    A fetch failure on one instrument (e.g. a rate-limit hiccup) is isolated to
    that instrument -- the rest of the basket still gets checked this round.
    """
    by_instrument: dict[str, list[TradingLine]] = {}
    for line in lines:
        by_instrument.setdefault(line.instrument, []).append(line)

    now = datetime.now(timezone.utc)
    results = []
    errors = []
    for instrument, instrument_lines in by_instrument.items():
        try:
            await sync_candles(client, store, instrument, granularity="daily", count=200)
            candles = await store.get_candles(instrument, "daily", now - timedelta(days=400), now)
        except AlphaVantageError as e:
            logger.warning("[%s] Alpha Vantage-feil, hopper over denne runden: %s", instrument, e)
            errors.append(f"{instrument}: {e}")
            continue
        for line in instrument_lines:
            results.append(await evaluate_line(executor, line, candles))
    return results, errors


async def _publish_status(
    publisher: GithubStatusPublisher,
    lines: list[TradingLine],
    kill_switch: KillSwitch,
    error: str | None,
) -> None:
    def line_equity(line: TradingLine) -> float:
        return line.portfolio.equity_curve[-1] if line.portfolio.equity_curve else line.portfolio.starting_cash

    status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kill_switch_triggered": kill_switch.is_triggered,
        "kill_switch_reason": kill_switch.reason,
        "error": error,
        "total_equity": sum(line_equity(line) for line in lines),
        "lines": [
            {
                "instrument": line.instrument,
                "strategy": line.strategy.name,
                "in_position": line.in_position,
                "equity": line_equity(line),
            }
            for line in lines
        ],
    }
    try:
        await publisher.publish(status)
    except Exception as e:  # a status-publish hiccup should never crash the bot
        logger.warning("Klarte ikke publisere status til GitHub: %s", e)


def _build_lines(instruments: list[str], starting_cash_total: float, kill_switch: KillSwitch) -> list[TradingLine]:
    factories = strategy_factories()
    per_line_cash = starting_cash_total / (len(instruments) * len(factories))

    lines = []
    for instrument in instruments:
        for factory in factories:
            strategy = factory()
            gatekeeper = RiskGatekeeper(RiskLimits(), kill_switch)
            lines.append(
                TradingLine(
                    instrument=instrument,
                    strategy=strategy,
                    gatekeeper=gatekeeper,
                    risk_window=DailyRiskWindow(gatekeeper),
                    portfolio=Portfolio(starting_cash=per_line_cash),
                )
            )
    return lines


async def main() -> None:
    load_dotenv()

    client = AlphaVantageClient(api_key=os.environ["ALPHA_VANTAGE_API_KEY"])
    store = CandleStore(os.environ["DATABASE_URL"])
    await store.connect()

    instruments_env = os.environ.get("INSTRUMENTS", ",".join(DEFAULT_INSTRUMENTS))
    instruments = [s.strip() for s in instruments_env.split(",") if s.strip()]

    default_interval = int(24 * 60 * 60 * len(instruments) / TARGET_CALLS_PER_DAY)
    check_interval_seconds = int(os.environ.get("CHECK_INTERVAL_SECONDS", default_interval))
    starting_cash_total = float(os.environ.get("STARTING_CASH", "10000"))

    kill_switch = KillSwitch()
    lines = _build_lines(instruments, starting_cash_total, kill_switch)
    executor = BacktestExecutor()

    github_token = os.environ.get("GITHUB_TOKEN")
    status_publisher = (
        GithubStatusPublisher(token=github_token, owner=STATUS_REPO_OWNER, repo=STATUS_REPO_NAME)
        if github_token
        else None
    )

    logger.info(
        "Trading-bot startet (paper trading, %d instrumenter x %d strategier = %d linjer, sjekk hvert %ds)",
        len(instruments),
        len(lines) // len(instruments),
        len(lines),
        check_interval_seconds,
    )

    try:
        while True:
            if kill_switch.is_triggered:
                logger.warning("Kill switch aktivert (%s) - stopper handel.", kill_switch.reason)
                if status_publisher is not None:
                    await _publish_status(status_publisher, lines, kill_switch, error=None)
                break

            _, errors = await check_all(client, store, executor, lines)
            error = "; ".join(errors) if errors else None

            if status_publisher is not None:
                await _publish_status(status_publisher, lines, kill_switch, error)

            await asyncio.sleep(check_interval_seconds)
    finally:
        await client.close()
        await store.close()
        if status_publisher is not None:
            await status_publisher.close()


if __name__ == "__main__":
    asyncio.run(main())
