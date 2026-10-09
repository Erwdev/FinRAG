"""Retry untuk panggilan HTTP keluar (Improvisation D4, D5). Memakai tenacity yang sudah dideklarasikan di pyproject.

Hanya kegagalan sementara yang diulang: error transport, 429, dan 5xx. Error 4xx lain (kunci salah, kuota habis,
permintaan tidak valid) langsung dilempar, karena mengulangnya tidak mengubah hasil dan bisa membuang kredit.
"""

from __future__ import annotations

import httpx
import tenacity


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    # httpx.HTTPStatusError membawa response; SDK Pinecone membawa atribut status.
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None) or getattr(exc, "status", None)
    if isinstance(status, int):
        return status == 429 or status >= 500
    return isinstance(exc, (TimeoutError, ConnectionError))


def transient_retry(attempts: int = 3):
    return tenacity.retry(
        reraise=True,
        stop=tenacity.stop_after_attempt(attempts),
        wait=tenacity.wait_exponential(multiplier=0.5, max=4),
        retry=tenacity.retry_if_exception(is_transient),
    )
