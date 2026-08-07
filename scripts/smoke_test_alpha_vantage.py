"""Standalone smoke test for the Alpha Vantage client.

Run this outside the Claude Code sandbox (locally, or on the VPS) where
alphavantage.co isn't blocked by network policy:

    ALPHA_VANTAGE_API_KEY=your-key python scripts/smoke_test_alpha_vantage.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.alpha_vantage import AlphaVantageClient, AlphaVantageError  # noqa: E402


async def main() -> None:
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        print("Sett ALPHA_VANTAGE_API_KEY i miljøet først.")
        return

    client = AlphaVantageClient(api_key=api_key)
    try:
        candles = await client.fetch_candles("EUR_USD", granularity="daily", count=10)
        print(f"Hentet {len(candles)} candles")
        if candles:
            last = candles[-1]
            print(f"Siste: {last.timestamp} O={last.open} H={last.high} L={last.low} C={last.close}")
    except AlphaVantageError as e:
        print(f"AlphaVantageError: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
