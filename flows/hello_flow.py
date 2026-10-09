"""Flow hello untuk mengukur menit Prefect Serverless (Architecture.md 13, jam 0 sampai 2).

Tidak memanggil layanan eksternal. Mencatat waktu agar bisa dibandingkan dengan asumsi 4.5.
"""

import platform
import time

from prefect import flow, get_run_logger


@flow(name="hello-flow", retries=0)
def hello_flow() -> dict:
    log = get_run_logger()
    started = time.perf_counter()
    info = {"python": platform.python_version(), "platform": platform.platform()}
    log.info("hello from Prefect Serverless: %s", info)
    info["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return info


if __name__ == "__main__":
    print(hello_flow())
