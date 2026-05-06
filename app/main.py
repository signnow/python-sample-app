from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routing import router
from app.settings import settings  # noqa: F401 — triggers .env load at import

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

_STATIC = Path(__file__).parent.parent / "static"

app = FastAPI(title="SignNow Python Sample App")

app.mount("/css", StaticFiles(directory=_STATIC / "css"), name="css")
app.mount("/js", StaticFiles(directory=_STATIC / "js"), name="js")
app.mount("/img", StaticFiles(directory=_STATIC / "img"), name="img")
app.mount("/fonts", StaticFiles(directory=_STATIC / "fonts"), name="fonts")
app.mount("/assets", StaticFiles(directory=_STATIC / "assets"), name="assets")

app.include_router(router)
