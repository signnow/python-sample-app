from __future__ import annotations

import importlib
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from app.sample_interface import SampleController

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[a-zA-Z0-9_]+$")
_ERROR_HTML_PATH = Path(__file__).parent.parent / "static" / "error.html"
_SAMPLES_DIR = Path(__file__).parent.parent / "samples"


def is_valid_sample_name(name: str) -> bool:
    return bool(_NAME_RE.match(name))


def discover_samples() -> list[str]:
    """Return alphabetically sorted names of every folder under samples/ that has an index_controller.py."""
    if not _SAMPLES_DIR.is_dir():
        return []
    names = []
    for child in _SAMPLES_DIR.iterdir():
        if not child.is_dir() or child.name.startswith("_") or child.name.startswith("."):
            continue
        if not is_valid_sample_name(child.name):
            continue
        if (child / "index_controller.py").is_file():
            names.append(child.name)
    return sorted(names)


def load_controller(name: str) -> SampleController | None:
    if not is_valid_sample_name(name):
        return None
    try:
        module = importlib.import_module(f"samples.{name}.index_controller")
    except ImportError:
        return None
    cls = getattr(module, "IndexController", None)
    if cls is None:
        return None
    try:
        instance = cls()
    except Exception:
        logger.exception("Failed to instantiate %s.IndexController", name)
        return None
    return instance if isinstance(instance, SampleController) else None


def _error_404() -> HTMLResponse:
    try:
        html = _ERROR_HTML_PATH.read_text()
    except FileNotFoundError:
        html = "<h1>404 Not Found</h1>"
    return HTMLResponse(content=html, status_code=404)


router = APIRouter()


@router.get("/", include_in_schema=False)
def root() -> Response:
    return _error_404()


@router.get("/api/samples")
def api_samples_list() -> Response:
    return JSONResponse({"samples": discover_samples()})


@router.get("/samples", include_in_schema=False)
def samples_index() -> Response:
    names = discover_samples()
    items = "\n".join(
        f'      <li><a href="/samples/{n}">{n}</a></li>' for n in names
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SignNow Python Sample App — Samples</title>
  <link href="/css/bootstrap.min.css" rel="stylesheet">
  <link href="/css/styles.css" rel="stylesheet">
  <link rel="icon" href="/img/sign-now.png">
  <style>
    body {{ padding: 2rem; font-family: "Open Sans", system-ui, sans-serif; }}
    .wrap {{ max-width: 720px; margin: 0 auto; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .sub {{ color: #666; margin-bottom: 1.5rem; }}
    ul {{ list-style: none; padding: 0; }}
    li {{ padding: 0.5rem 0; border-bottom: 1px solid #eee; }}
    a {{ color: #047cc0; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .count {{ color: #888; font-size: 0.9em; }}
    img.logo {{ height: 36px; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <div class="wrap">
    <img class="logo" src="/img/sign-now.png" alt="SignNow">
    <h1>Available Samples</h1>
    <p class="sub"><span class="count">{len(names)} samples</span> · JSON at <code>/api/samples</code></p>
    <ul>
{items}
    </ul>
  </div>
</body>
</html>
"""
    return HTMLResponse(html)


@router.get("/samples/{name}")
def route_get(name: str, request: Request) -> Response:
    controller = load_controller(name)
    if controller is None:
        return _error_404()
    try:
        return controller.handle_get(dict(request.query_params))
    except Exception as e:
        logger.exception("handle_get failed for sample %s", name)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/samples/{name}")
async def route_post(name: str, request: Request) -> Response:
    controller = load_controller(name)
    if controller is None:
        return _error_404()

    content_type = request.headers.get("content-type", "")
    body: dict[str, Any]
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        body = dict(form)
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}

    try:
        return controller.handle_post(body)
    except Exception as e:
        logger.exception("handle_post failed for sample %s", name)
        return JSONResponse({"error": str(e)}, status_code=500)
