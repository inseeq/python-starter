import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.inseeq import InseeqError, get_client, load_env

QUERY_NAME = "daily_digest"
MAX_LINES = 20
MAX_AGE = timedelta(hours=48)
SLACK_TIMEOUT_SECONDS = 30


def post_to_slack(text: str) -> None:
    try:
        response = httpx.post(os.environ["SLACK_WEBHOOK_URL"], json={"text": text}, timeout=SLACK_TIMEOUT_SECONDS)
    except httpx.HTTPError:
        raise InseeqError("slack_unreachable", "Could not reach the Slack webhook.") from None
    if not response.is_success:
        raise InseeqError("slack_error", f"Slack answered {response.status_code}: {response.text[:100]}", response.status_code)


def describe(row: dict[str, Any]) -> str:
    return ", ".join(f"{name}: {'null' if value is None else value}" for name, value in row.items())


def digest() -> None:
    if not os.environ.get("SLACK_WEBHOOK_URL"):
        sys.exit("SLACK_WEBHOOK_URL is not set.")
    client = get_client()

    status = client.status()
    refreshed_at = status["refreshed_at"]
    fresh = refreshed_at is not None and datetime.now(UTC) - datetime.fromisoformat(refreshed_at) <= MAX_AGE
    if status["last_failure"] or not fresh:
        post_to_slack(f"inseeq data is not fresh: last refresh {refreshed_at or 'never'}")
        sys.exit("The data is not fresh. Posted that to Slack instead of the digest.")

    day = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    result = client.run_saved(QUERY_NAME, params=[{"name": "day", "type": "DATE", "value": day}], row_limit=MAX_LINES)
    rows = result["rows"]
    lines = [describe(row) for row in rows] or ["No data."]
    if result["total_rows"] > len(rows):
        lines.append(f"and {result['total_rows'] - len(rows)} more rows")
    post_to_slack("\n".join([f"Yesterday ({day})", *lines]))
    print(f"Posted {len(rows)} lines for {day}.")


def main() -> None:
    load_env()
    try:
        digest()
    except InseeqError as error:
        sys.exit(f"{error.code}: {error.message}")


if __name__ == "__main__":
    main()
