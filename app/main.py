import os
from collections.abc import AsyncIterable
from typing import Any
from urllib.parse import parse_qs

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from standardwebhooks import Webhook, WebhookVerificationError

from app.inseeq import InseeqError, get_client, load_env
from app.pages import render_dashboard, render_error, render_login
from app.session import MAX_AGE_SECONDS, SESSION_COOKIE, constant_time_equal, create_session, is_local, is_valid_session

PUBLIC_PATHS = {"/login", "/api/login", "/webhooks/inseeq"}
MAX_BODY_BYTES = 1024 * 1024

load_env()
PASSWORD = os.environ.get("DASHBOARD_PASSWORD")
if not PASSWORD:
    raise SystemExit("DASHBOARD_PASSWORD is not set, so the app will not start. Run uv run cli.py setup in your own terminal.")

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def require_login(request: Request, call_next: Any) -> Response:
    path = request.url.path
    if path in PUBLIC_PATHS or is_valid_session(request.cookies.get(SESSION_COOKIE), PASSWORD):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"error": {"code": "unauthorized", "message": "Log in first."}}, status_code=401)
    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(error: str | None = None) -> str:
    return render_login(error is not None)


@app.post("/api/login")
async def login(request: Request) -> Response:
    form = parse_qs((await request.body()).decode("utf-8", "replace"))
    if not constant_time_equal(form.get("password", [""])[0], PASSWORD):
        return RedirectResponse("/login?error=1", status_code=303)
    response = RedirectResponse("/", status_code=303)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    response.set_cookie(
        SESSION_COOKIE,
        create_session(PASSWORD),
        max_age=MAX_AGE_SECONDS,
        path="/",
        httponly=True,
        samesite="lax",
        secure=not is_local(host),
    )
    return response


@app.post("/api/logout")
def logout() -> Response:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    try:
        client = get_client()
        return render_dashboard(client.status(), client.list_tables())
    except InseeqError as error:
        return render_error(error.code, error.message)


async def read_capped_body(stream: AsyncIterable[bytes]) -> bytes | None:
    body = bytearray()
    async for chunk in stream:
        body += chunk
        if len(body) > MAX_BODY_BYTES:
            return None
    return bytes(body)


def handle_event(event: dict[str, Any]) -> None:
    print(f"[inseeq] {event['type']} {event['id']}", flush=True)


@app.post("/webhooks/inseeq")
async def webhook(request: Request, background: BackgroundTasks) -> Response:
    secret = os.environ.get("INSEEQ_WEBHOOK_SECRET")
    if not secret:
        return JSONResponse({"error": "INSEEQ_WEBHOOK_SECRET is not set."}, status_code=503)
    body = await read_capped_body(request.stream())
    if body is None:
        return JSONResponse({"error": "The body is over 1 MiB."}, status_code=413)

    try:
        event = Webhook(secret).verify(body, request.headers)
    except (WebhookVerificationError, ValueError):
        return JSONResponse({"error": "The webhook signature does not verify."}, status_code=401)

    background.add_task(handle_event, event)
    return JSONResponse({"received": True})
