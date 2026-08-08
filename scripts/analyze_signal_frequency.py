"""Analyze how often each (instrument, strategy) line fires, using real historical
data, before trusting the live bot's frequency. Run this outside the Claude Code
sandbox (locally, or on the VPS) where alphavantage.co isn't blocked:

    ALPHA_VANTAGE_API_KEY=your-key python scripts/analyze_signal_frequency.py

Prints entries/week and backtest metrics per (instrument, strategy) line, plus a
combined total, so RSI/Bollinger/trend thresholds can be tuned against reality
before going live.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.alpha_vantage import AlphaVantageClient, AlphaVantageError  # noqa: E402
from execution.backtest_runner import run_backtest  # noqa: E402
from main import DEFAULT_INSTRUMENTS, strategy_factories  # noqa: E402
from risk.gatekeeper import RiskGatekeeper, RiskLimits  # noqa: E402
from risk.kill_switch import KillSwitch  # noqa: E402

TRADING_DAYS_PER_WEEK = 5


async def main() -> None:
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        print("Sett ALPHA_VANTAGE_API_KEY i miljøet først.")
        return

    client = AlphaVantageClient(api_key=api_key)
    rows = []
    total_entries = 0
    min_weeks = None

    try:
        for instrument in DEFAULT_INSTRUMENTS:
            try:
                candles = await client.fetch_candles(instrument, granularity="daily", count=500)
            except AlphaVantageError as e:
                print(f"{instrument}: feil ved henting ({e}), hopper over")
                continue

            if len(candles) < 60:
                print(f"{instrument}: for lite historikk ({len(candles)} candles), hopper over")
                continue

            weeks = len(candles) / TRADING_DAYS_PER_WEEK
            min_weeks = weeks if min_weeks is None else min(min_weeks, weeks)

            for factory in strategy_factories():
                strategy = factory()
                gatekeeper = RiskGatekeeper(RiskLimits(), KillSwitch())
                metrics = await run_backtest(strategy, gatekeeper, candles, starting_cash=10_000)
                signals = strategy.generate_signals(candles)
                num_entries = sum(signals.entries)
                total_entries += num_entries
                rows.append((instrument, strategy.name, num_entries, weeks, metrics))
    finally:
        await client.close()

    if not rows:
        print("Ingen resultater - sjekk API-nøkkel/rate-limit.")
        return

    header = f"{'Par':<10} {'Strategi':<16} {'Signaler':<10} {'Signaler/uke':<14} {'Vinnrate':<10} {'Avkastning':<12}"
    print(f"\n{header}")
    print("-" * len(header))
    for instrument, strategy_name, num_entries, weeks, metrics in rows:
        per_week = num_entries / weeks if weeks else 0
        print(
            f"{instrument:<10} {strategy_name:<16} {num_entries:<10} {per_week:<14.2f} "
            f"{metrics.win_rate:<10.1%} {metrics.total_return_pct:<12.1%}"
        )

    if min_weeks:
        print(f"\nTotalt: {total_entries} signaler over ~{min_weeks:.0f} uker (korteste historikk blant parene)")
        print(f"Snitt: {total_entries / min_weeks:.2f} signaler/uke samlet på tvers av alle par og strategier")


if __name__ == "__main__":
    asyncio.run(main())
