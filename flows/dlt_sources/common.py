"""Utilitas bersama untuk sumber dlt. Waktu disimpan sebagai UTC naif (bagian 4.3)."""

from datetime import datetime, timezone


def utc_naive_from_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(tzinfo=None)
