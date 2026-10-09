"""FastAPI finrag-api (Architecture.md 9.2). Dijalankan lewat Mangum di Lambda."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.routes import chat, charts, feed, handoffs, jobs, me, portfolio, prices, signals, status, universe
from app.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="FinRAG API",
        version="0.1.0",
        # Function URL bersifat publik. Dokumentasi OpenAPI tidak diekspos.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origin_list,
        allow_methods=["GET", "PUT", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,
    )

    @app.get("/health")
    async def health() -> dict:
        # Tanpa DB dan tanpa auth: dipakai uji URL hello dan EventBridge (bagian 3.1).
        return {"status": "ok", "service": "finrag-api"}

    app.include_router(me.router)
    app.include_router(universe.router)
    app.include_router(portfolio.router)
    app.include_router(charts.router)
    app.include_router(signals.router)
    app.include_router(prices.router)
    app.include_router(status.router)
    app.include_router(feed.router)
    app.include_router(chat.router)
    app.include_router(jobs.router)
    app.include_router(handoffs.router)
    return app


app = create_app()
