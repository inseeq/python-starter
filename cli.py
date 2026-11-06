import getpass
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlsplit

from app.inseeq import DEFAULT_API_URL, ENV_FILE, QUERIES_DIR, InseeqError, get_client, load_env

RECEIVER_PATH = "/webhooks/inseeq"
QUERY_ROW_LIMIT = 1_000


def save_env(updates: dict[str, str]) -> None:
    existing = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    kept = [line for line in existing if line and line.split("=")[0] not in updates]
    lines = kept + [f"{name}={value}" for name, value in updates.items()]
    temporary = Path(f"{ENV_FILE}.tmp")
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as file:
        file.write("\n".join(lines) + "\n")
    temporary.replace(ENV_FILE)


def setup() -> None:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        sys.exit("Setup needs a real terminal. Open your own in this folder and run: uv run cli.py setup")

    api_key = getpass.getpass("Paste your inseeq data key (it stays hidden): ").strip()
    if not api_key:
        sys.exit("No key entered, so nothing was changed.")

    api_url = os.environ.get("INSEEQ_API_URL") or DEFAULT_API_URL
    saved_password = os.environ.get("DASHBOARD_PASSWORD")
    password = saved_password or secrets.token_urlsafe(24)
    save_env({"INSEEQ_API_KEY": api_key, "INSEEQ_API_URL": api_url, "DASHBOARD_PASSWORD": password})
    print("Wrote .env and kept its DASHBOARD_PASSWORD." if saved_password else f"Wrote .env. Dashboard password, shown once: {password}")

    client = Client(api_key, api_url)
    status, tables = client.status(), client.list_tables()
    print(f"Connected. {len(tables)} tables. Last refresh: {status['refreshed_at'] or 'not recorded yet'}.")


def query(sql_or_name: str | None = None) -> None:
    if not sql_or_name:
        sys.exit('Usage: uv run cli.py query "select 1 as ok", or the name of a file in queries/')
    file = QUERIES_DIR / f"{sql_or_name}.sql"
    sql = file.read_text() if file.exists() else sql_or_name
    result = get_client().query(sql, row_limit=QUERY_ROW_LIMIT)
    print(json.dumps(result, indent=2))
    if result["truncated"]:
        print(f"Stopped at {QUERY_ROW_LIMIT} rows. Aggregate in SQL, or call client.query from code.", file=sys.stderr)


def register_webhook(address: str) -> None:
    parts = urlsplit(address)
    if not parts.scheme or not parts.netloc:
        sys.exit(f"Not a URL: {address}")
    url = parts._replace(path=RECEIVER_PATH).geturl() if parts.path in ("", "/") else address
    client = get_client()
    existing = next((webhook for webhook in client.list_webhooks() if webhook["url"] == url), None)
    if existing:
        sys.exit(f"{url} is already registered as {existing['id']}. Send DELETE /v1/webhooks/{existing['id']} first to get a new secret.")

    created = client.create_webhook(url)
    save_env({"INSEEQ_WEBHOOK_SECRET": created["secret"]})
    print(f"Registered {url} as {created['id']}. Wrote INSEEQ_WEBHOOK_SECRET to .env.")
    print("The app reads .env only when it starts, and --reload does not watch it. It answers 503 until you restart it. On a host, set the secret and redeploy.")
    print(f"Then run: uv run cli.py webhook test {created['id']}")


def test_webhook(webhook_id: str) -> None:
    answer = get_client().test_webhook(webhook_id)
    if not answer["delivered"]:
        sys.exit(f"Not delivered. The receiver answered {answer['status'] or 'nothing'}.")
    print(f"Delivered. The receiver answered {answer['status']}.")


WEBHOOK_COMMANDS = {"register": register_webhook, "test": test_webhook}


def webhook(subcommand: str = "", argument: str = "") -> None:
    if subcommand not in WEBHOOK_COMMANDS or not argument:
        sys.exit("Usage: uv run cli.py webhook register <url> | test <id>")
    WEBHOOK_COMMANDS[subcommand](argument)


COMMANDS = {"setup": setup, "query": query, "webhook": webhook}


def main() -> None:
    command, *args = sys.argv[1:] or [""]
    if command not in COMMANDS:
        sys.exit(f"Commands: {', '.join(COMMANDS)}")
    load_env()
    try:
        COMMANDS[command](*args)
    except InseeqError as error:
        sys.exit(f"{error.code}: {error.message}")
    except (KeyboardInterrupt, EOFError):
        sys.exit(130)


if __name__ == "__main__":
    main()
