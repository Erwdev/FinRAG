"""Verifikasi JWT Clerk (Architecture.md 9.1): JWKS, RS256, exp, nbf, issuer, azp."""

from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.settings import Settings


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    # Kunci JWKS di-cache 1 jam di dalam klien; invocation hangat memakai ulang klien.
    return PyJWKClient(url, cache_keys=True, lifespan=3600)


class TokenError(Exception):
    pass


def verify_clerk_token(token: str, settings: Settings) -> dict:
    try:
        signing_key = _jwks_client(settings.clerk_jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            options={"require": ["exp", "nbf", "sub", "iss"]},
        )
    except (jwt.PyJWTError, OSError) as exc:
        raise TokenError(str(exc)) from exc

    azp = claims.get("azp")
    if azp is not None and azp not in settings.allowed_origin_list:
        raise TokenError(f"azp not allowed: {azp}")
    return claims
