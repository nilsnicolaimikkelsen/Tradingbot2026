"""Splits historical candles into rolling train/test windows for walk-forward validation."""

from dataclasses import dataclass

from data.models import Candle


@dataclass(frozen=True)
class WalkForwardWindow:
    train: list[Candle]
    test: list[Candle]


def walk_forward_windows(
    candles: list[Candle], train_size: int, test_size: int, step: int | None = None
) -> list[WalkForwardWindow]:
    """Roll a train/test window forward across `candles`.

    Each window's test slice immediately follows its train slice, so test is
    always out-of-sample relative to the preceding train period. Reoptimizing
    strategy parameters on `train` and evaluating on `test` (per CLAUDE.md §2)
    is left to the caller — this only produces the splits.
    """
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train_size and test_size must be positive")
    step = step or test_size

    windows = []
    start = 0
    while start + train_size + test_size <= len(candles):
        train = candles[start : start + train_size]
        test = candles[start + train_size : start + train_size + test_size]
        windows.append(WalkForwardWindow(train=train, test=test))
        start += step
    return windows
