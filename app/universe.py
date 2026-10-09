"""Universe aset tetap (Architecture.md 4.4), dibaca dari config/universe.yaml."""

from functools import lru_cache
from pathlib import Path

import yaml

# app/universe.py -> akar proyek (lokal) atau /var/task (Lambda, config/ disalin Dockerfile)
UNIVERSE_PATH = Path(__file__).resolve().parent.parent / "config" / "universe.yaml"


@lru_cache(maxsize=1)
def load_universe() -> tuple[dict, ...]:
    raw = yaml.safe_load(UNIVERSE_PATH.read_text(encoding="utf-8")) or []
    symbols = [c["symbol"] for c in raw]
    if len(symbols) != len(set(symbols)):
        raise ValueError("config/universe.yaml: symbol duplikat")
    if len(symbols) > 10:
        raise ValueError("config/universe.yaml: universe maksimum 10 koin (PL-1)")
    return tuple(raw)


def universe_symbols() -> set[str]:
    return {c["symbol"] for c in load_universe()}
