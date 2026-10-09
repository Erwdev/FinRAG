"""Indikator murni tanpa pandas (Architecture.md 4.3 dan 11.1).

EMA dihitung di sini karena rekursi tidak praktis di dbt. SMA, Bollinger, ROC, drawdown, dan stdev
memakai rumus yang sama dengan model mart_indicators (dbt) agar angka konsisten.
"""

from __future__ import annotations

import math


def sma(values: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    for i in range(n - 1, len(values)):
        out[i] = sum(values[i - n + 1 : i + 1]) / n
    return out


def stdev_pop(window: list[float]) -> float:
    m = sum(window) / len(window)
    return math.sqrt(sum((x - m) ** 2 for x in window) / len(window))


def rolling_stdev(values: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    for i in range(n - 1, len(values)):
        out[i] = stdev_pop(values[i - n + 1 : i + 1])
    return out


def ema(values: list[float], span: int) -> list[float]:
    """ema_t = alpha * close_t + (1 - alpha) * ema_(t-1), alpha = 2 / (span + 1), seed = nilai pertama."""
    if not values:
        return []
    alpha = 2.0 / (span + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


def bollinger(values: list[float], n: int = 20, k: float = 2.0):
    mid = sma(values, n)
    sd = rolling_stdev(values, n)
    upper = [None if m is None else m + k * s for m, s in zip(mid, sd)]
    lower = [None if m is None else m - k * s for m, s in zip(mid, sd)]
    return lower, upper


def roc_pct(values: list[float], n: int = 20) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    for i in range(n, len(values)):
        if values[i - n] != 0:
            out[i] = (values[i] / values[i - n] - 1) * 100
    return out


def drawdown_pct(values: list[float], window: int = 252) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    for i in range(len(values)):
        hi = max(values[max(0, i - window + 1) : i + 1])
        out[i] = (values[i] / hi - 1) * 100 if hi else None
    return out


def returns_stdev_pct(values: list[float], n: int = 20) -> list[float | None]:
    rets = [None] + [
        (values[i] / values[i - 1] - 1) if values[i - 1] else None for i in range(1, len(values))
    ]
    out: list[float | None] = [None] * len(values)
    for i in range(n, len(values)):
        window = rets[i - n + 1 : i + 1]
        if all(w is not None for w in window):
            out[i] = stdev_pop(window) * 100
    return out


def chart_series(closes: list[float]) -> list[dict]:
    """Seri per titik untuk grafik: SMA20, SMA50, EMA12, EMA26, Bollinger(20,2)."""
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    lower, upper = bollinger(closes, 20, 2.0)
    return [
        {
            "close": round(closes[i], 8),
            "sma20": _r(sma20[i]),
            "sma50": _r(sma50[i]),
            "ema12": _r(ema12[i]),
            "ema26": _r(ema26[i]),
            "bb_lower": _r(lower[i]),
            "bb_upper": _r(upper[i]),
        }
        for i in range(len(closes))
    ]


def _r(x: float | None) -> float | None:
    return None if x is None else round(x, 8)
