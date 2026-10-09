"""Sinyal indikator deskriptif (Architecture.md 9.2 dan 10.4).

Hanya deskripsi data, bukan saran. Input adalah baris terakhir mart_indicators.
"""

from __future__ import annotations


def describe(snapshot: dict) -> dict:
    close = snapshot.get("close")
    items: list[dict] = []

    sma50 = snapshot.get("sma50")
    if close is not None and sma50 is not None:
        if close > sma50:
            items.append({"code": "above_sma50", "text": "harga di atas SMA50"})
        else:
            items.append({"code": "below_sma50", "text": "harga di bawah SMA50"})

    band_pos = snapshot.get("band_pos")
    if band_pos is not None:
        if band_pos >= 0.8:
            items.append({"code": "near_upper_band", "text": "dekat batas atas Bollinger"})
        elif band_pos <= 0.2:
            items.append({"code": "near_lower_band", "text": "dekat batas bawah Bollinger"})

    roc20 = snapshot.get("roc20_pct")
    if roc20 is not None:
        if roc20 >= 10:
            items.append({"code": "momentum_strong_up", "text": "momentum 20 hari kuat naik"})
        elif roc20 <= -10:
            items.append({"code": "momentum_strong_down", "text": "momentum 20 hari kuat turun"})

    dd = snapshot.get("drawdown_252_pct")
    if dd is not None and dd <= -20:
        items.append({"code": "deep_drawdown", "text": "drawdown dalam dari tertinggi 252 hari"})

    return {
        "ticker": snapshot.get("ticker"),
        "as_of": str(snapshot.get("trade_date")) if snapshot.get("trade_date") is not None else None,
        "signals": items,
    }
