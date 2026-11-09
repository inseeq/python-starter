import os
import random
import re
import time
from functools import lru_cache
from itertools import count
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

DEFAULT_API_URL = "https://api.inseeq.com"
ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
QUERIES_DIR = ROOT / "queries"

MAX_RETRIES = 5
MAX_RETRY_WAIT_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 90
LIST_PAGE_SIZE = 100
QUERY_PAGE_SIZE = 5_000
DEFAULT_ROW_LIMIT = 10_000


class InseeqError(Exception):
    def __init__(self, code: str, message: str, status: int = 0, resets_at: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.resets_at = resets_at


class Client:
    def __init__(self, api_key: str, api_url: str | None = None):
        self._url = (api_url or DEFAULT_API_URL).rstrip("/")
        self._http = httpx.Client(headers={"Authorization": f"Bearer {api_key}"}, timeout=REQUEST_TIMEOUT_SECONDS)

    def _request(self, method: str, route: str, *, body: Any = None, params: dict[str, Any] | None = None) -> Any:
        for attempt in count():
            try:
                response = self._http.request(method, f"{self._url}/v1{route}", json=body, params=params)
            except httpx.HTTPError:
                raise InseeqError("unreachable", f"Could not reach {self._url}.") from None

            try:
                payload = response.json() if response.content else None
            except ValueError:
                if response.is_success:
                    message = f"{self._url} did not answer JSON. Check INSEEQ_API_URL."
                    raise InseeqError("unexpected_response", message, response.status_code) from None
                payload = None
            if response.is_success:
                return payload

            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            code = error.get("code", "unexpected_response")
            retry_after = response.headers.get("retry-after", "")
            wait = (int(retry_after) if retry_after.isdecimal() else 2**attempt) + random.random()
            retryable = code in ("rate_limited", "busy", "internal_error") or response.status_code == 503
            if not retryable or attempt >= MAX_RETRIES or wait > MAX_RETRY_WAIT_SECONDS:
                message = error.get("message", f"The API answered {response.status_code}.")
                raise InseeqError(code, message, response.status_code, error.get("resets_at"))
            time.sleep(wait)

    def list_tables(self) -> list[dict[str, Any]]:
        tables = []
        after = None
        while True:
            params = {"limit": LIST_PAGE_SIZE} | ({"after": after} if after else {})
            page = self._request("GET", "/tables", params=params)
            tables.extend(page["tables"])
            after = page["next_after"]
            if not after:
                return tables

    def get_table(self, name: str) -> dict[str, Any]:
        return self._request("GET", f"/tables/{quote(name, safe='')}")

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/status")

    def query(self, sql: str, *, params: list[dict[str, str]] | None = None, row_limit: int = DEFAULT_ROW_LIMIT) -> dict[str, Any]:
        body = {"sql": sql, "max_rows": min(QUERY_PAGE_SIZE, row_limit)} | ({"params": params} if params else {})
        first = self._request("POST", "/query", body=body)
        cursor = first.pop("next_cursor")
        rows = first["rows"]
        while cursor and len(rows) < row_limit:
            page = self._request("GET", "/query/results", params={"cursor": cursor})
            rows.extend(page["rows"])
            cursor = page["next_cursor"]
        kept = rows[:row_limit]
        return first | {"rows": kept, "row_count": len(kept), "truncated": cursor is not None or len(rows) > row_limit}

    def run_saved(self, name: str, **options: Any) -> dict[str, Any]:
        if not re.fullmatch(r"[\w-]+", name):
            raise ValueError(f"Not a saved query name: {name}")
        return self.query((QUERIES_DIR / f"{name}.sql").read_text(), **options)

    def create_webhook(self, url: str) -> dict[str, Any]:
        return self._request("POST", "/webhooks", body={"url": url})

    def list_webhooks(self) -> list[dict[str, Any]]:
        return self._request("GET", "/webhooks")["webhooks"]

    def test_webhook(self, webhook_id: str) -> dict[str, Any]:
        return self._request("POST", f"/webhooks/{quote(webhook_id, safe='')}/test")


def load_env() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        name, separator, value = line.partition("=")
        if separator and not name.startswith("#"):
            os.environ.setdefault(name.strip(), value.strip().strip("'\""))


@lru_cache(maxsize=1)
def get_client() -> Client:
    api_key = os.environ.get("INSEEQ_API_KEY")
    if not api_key:
        raise InseeqError("missing_key", "INSEEQ_API_KEY is not set. Run uv run cli.py setup --from-clipboard.")
    return Client(api_key, os.environ.get("INSEEQ_API_URL"))
