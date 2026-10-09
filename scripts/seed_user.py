"""Isi app_user secara manual untuk pemilik (Architecture.md 9.1 dan 3.3).

Tidak ada endpoint pembuatan pengguna. Jalankan dari akar repositori:
    uv run python -m scripts.seed_user --clerk-user-id user_XXXX --email you@example.com

DATABASE_URL diambil dari environment shell (bukan dari berkas .env).
Idempoten: jika clerk_user_id sudah ada, email diperbarui dan is_active diset true.
"""

import argparse
import asyncio
import os
import sys

from sqlalchemy import text

from app.infra.postgres import make_engine


async def seed(clerk_user_id: str, email: str) -> None:
    raw_url = os.environ.get("DATABASE_URL")
    if not raw_url:
        raise SystemExit("DATABASE_URL belum diset di environment shell")

    engine = make_engine(raw_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO app_user (clerk_user_id, email, role, is_active)
                    VALUES (:clerk_user_id, :email, 'owner', true)
                    ON CONFLICT (clerk_user_id)
                    DO UPDATE SET email = EXCLUDED.email, is_active = true, role = 'owner'
                    """
                ),
                {"clerk_user_id": clerk_user_id, "email": email},
            )
    finally:
        await engine.dispose()
    print(f"seeded owner: clerk_user_id={clerk_user_id} email={email}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the single FinRAG owner row")
    parser.add_argument("--clerk-user-id", required=True, help="sub dari Clerk, contoh user_XXXX")
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    asyncio.run(seed(args.clerk_user_id, args.email))
    return 0


if __name__ == "__main__":
    sys.exit(main())
