"""Dependensi FastAPI untuk pemilik (Architecture.md 9.1).

Alur: Bearer JWT Clerk valid -> lookup app_user berdasarkan sub (cache memori 5 menit)
-> jika tidak ada atau tidak aktif atau role bukan owner: 403.
Token tidak valid: 401. Tidak ada token: 401.
"""

import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk import TokenError, verify_clerk_token
from app.db.models import AppUser
from app.db.session import get_session
from app.settings import get_settings

CACHE_TTL_SECONDS = 300
_bearer = HTTPBearer(auto_error=False)
_user_cache: dict[str, tuple[float, "CurrentUser"]] = {}


@dataclass(frozen=True)
class CurrentUser:
    id: str
    clerk_user_id: str
    email: str
    role: str


async def get_current_owner(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")

    try:
        claims = verify_clerk_token(creds.credentials, get_settings())
    except TokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")

    sub = claims["sub"]
    now = time.monotonic()
    cached = _user_cache.get(sub)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    row = (
        await session.execute(select(AppUser).where(AppUser.clerk_user_id == sub))
    ).scalar_one_or_none()
    # Kegagalan lookup tidak di-cache: akun yang baru di-seed langsung bisa masuk.
    if row is None or not row.is_active or row.role != "owner":
        _user_cache.pop(sub, None)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account is not registered")

    user = CurrentUser(id=str(row.id), clerk_user_id=row.clerk_user_id, email=row.email, role=row.role)
    _user_cache[sub] = (now, user)
    return user
