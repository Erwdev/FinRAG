"""Tool terparameter untuk agent (Architecture.md 5.2). Semua akses MotherDuck lewat run_query (token RO, batas detik)."""

from __future__ import annotations

from app.indicators import ema
from app.md import check_readonly_sql, run_query
from app.sources.prices import latest_prices

MAX_HISTORY_DAYS = 365


def get_indicators(rd, tickers: list[str]) -> list[dict]:
    """Baris indikator bar tertutup terbaru per ticker, plus EMA12 dan EMA26 dari fungsi Python."""
    if not tickers:
        return []
    marks = ", ".join("?" for _ in tickers)
    cols, rows = run_query(
        rd,
        "SELECT ticker, trade_date, close, sma20, sma50, sma200, bb_upper, bb_lower, band_pos, "
        "stdev20_pct, roc20_pct, drawdown_252_pct "
        "FROM finrag.mart.mart_indicators "
        f"WHERE ticker IN ({marks}) "
        "QUALIFY row_number() OVER (PARTITION BY ticker ORDER BY trade_date DESC) = 1",
        list(tickers),
    )
    out = [dict(zip(cols, r)) for r in rows]

    # Satu query untuk seluruh ticker (bukan satu query per ticker) agar compute MotherDuck tidak terbuang.
    closes_by_ticker = _closes_many(rd, tickers, 120)
    for item in out:
        closes = closes_by_ticker.get(item["ticker"], [])
        item["ema12"] = round(ema(closes, 12)[-1], 8) if closes else None
        item["ema26"] = round(ema(closes, 26)[-1], 8) if closes else None
        item["as_of"] = str(item.pop("trade_date"))
    return out


def get_price_history(rd, ticker: str, days: int) -> list[dict]:
    days = max(1, min(days, MAX_HISTORY_DAYS))
    dates, closes = _closes(rd, ticker, days)
    return [{"date": d, "close": c} for d, c in zip(dates, closes)]


def get_last_prices(tickers: list[str]) -> dict[str, dict]:
    """Harga terakhir dari PriceSource (Binance, lalu CoinGecko)."""
    return latest_prices(tickers)


def get_portfolio(holdings: list[dict], prices: dict[str, dict]) -> dict:
    """holdings: [{ticker, quantity, avg_cost}]. Nilai dan bobot dihitung di server dari harga terakhir."""
    positions = []
    total = 0.0
    for h in holdings:
        px = prices.get(h["ticker"], {}).get("price")
        value = float(h["quantity"]) * px if px is not None else None
        if value is not None:
            total += value
        positions.append(
            {
                "ticker": h["ticker"],
                "quantity": float(h["quantity"]),
                "avg_cost": None if h.get("avg_cost") is None else float(h["avg_cost"]),
                "last_price": px,
                "value": round(value, 2) if value is not None else None,
            }
        )
    for p in positions:
        p["weight_pct"] = round(p["value"] / total * 100, 1) if p["value"] and total else None
    return {"positions": positions, "total_value": round(total, 2)}


def run_readonly_sql(rd, sql: str) -> tuple[list[str], list[tuple]]:
    """Cadangan pertanyaan ad hoc. SQL guard wajib lolos sebelum sampai ke MotherDuck."""
    return run_query(rd, check_readonly_sql(sql))


def _closes(rd, ticker: str, n: int) -> tuple[list[str], list[float]]:
    _, rows = run_query(
        rd,
        "SELECT trade_date, close FROM finrag.mart.mart_ohlcv_1d "
        "WHERE ticker = ? AND is_closed ORDER BY trade_date DESC LIMIT ?",
        [ticker, n],
    )
    rows.reverse()
    return [str(r[0]) for r in rows], [float(r[1]) for r in rows]


def _closes_many(rd, tickers: list[str], n: int) -> dict[str, list[float]]:
    """n close terakhir per ticker dalam satu query, urut kronologis."""
    marks = ", ".join("?" for _ in tickers)
    _, rows = run_query(
        rd,
        "SELECT ticker, close FROM ("
        "  SELECT ticker, trade_date, close, "
        "         row_number() OVER (PARTITION BY ticker ORDER BY trade_date DESC) AS rn "
        "  FROM finrag.mart.mart_ohlcv_1d "
        f"  WHERE ticker IN ({marks}) AND is_closed"
        ") WHERE rn <= ? ORDER BY ticker, rn DESC",
        [*tickers, n],
    )
    out: dict[str, list[float]] = {}
    for ticker, close in rows:
        out.setdefault(ticker, []).append(float(close))
    return out
