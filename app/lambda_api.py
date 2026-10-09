"""Handler Lambda finrag-api (Architecture.md 3.1)."""

from mangum import Mangum

from app.main import app

# lifespan off: Lambda tidak menjalankan startup/shutdown ASGI. Koneksi dibuat lazy.
handler = Mangum(app, lifespan="off")
