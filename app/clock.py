"""Waktu UTC sebagai string ISO. Dipakai lintas domain (route, worker, Redis), jadi tidak tinggal di modul klien."""

import datetime as dt


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
