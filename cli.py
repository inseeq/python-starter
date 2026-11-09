import getpass
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from app.data import DEFAULT_RANGE, get_period
from app.format import time_ago
from app.inseeq import DEFAULT_API_URL, ENV_FILE, QUERIES_DIR, ROOT, Client, InseeqError, get_client, load_env

RECEIVER_PATH = "/webhooks/inseeq"
QUERY_ROW_LIMIT = 1_000
KEY_PREFIX = "inseeq_dk_"
CLIPBOARD_TIMEOUT_SECONDS = 10
VERCEL_NAMES = ("INSEEQ_API_KEY", "DASHBOARD_PASSWORD", "INSEEQ_WEBHOOK_SECRET")
PARAMETER = re.compile(r"(?<![\w@])@(\w+)")

# The platform's own clipboard tools, tried in turn.
CLIPBOARD = {
    "read": {
        "darwin": [["pbpaste"]],
        "win32": [["powershell", "-NoProfile", "-Command", "Get-Clipboard"]],
        "linux": [["wl-paste", "-n"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b", "-o"]],
    },
    "write": {
        "darwin": [["pbcopy"]],
        "win32": [["clip"]],
        "linux": [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-b", "-i"]],
    },
}


def save_env(updates: dict[str, str]) -> None:
    existing = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    kept = [line for line in existing if line and line.split("=")[0] not in updates]
    lines = kept + [f"{name}={value}" for name, value in updates.items()]
    temporary = Path(f"{ENV_FILE}.tmp")
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as file:
        file.write("\n".join(lines) + "\n")
    temporary.replace(ENV_FILE)


def read_clipboard() -> str | None:
    for command in CLIPBOARD["read"].get(sys.platform, []):
        try:
            run = subprocess.run(command, check=False, capture_output=True, text=True, timeout=CLIPBOARD_TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if run.returncode == 0:
            return run.stdout
    return None


def write_clipboard(value: str) -> bool:
    # No pipes for output: xclip stays behind to serve the selection and would hold them open.
    for command in CLIPBOARD["write"].get(sys.platform, []):
        try:
            run = subprocess.run(
                command,
                check=False,
                input=value,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=CLIPBOARD_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if run.returncode == 0:
            return True
    return False


def ask_for_key() -> str:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        sys.exit("Setup needs a real terminal, or the key on the clipboard: uv run cli.py setup --from-clipboard")
    api_key = getpass.getpass("Paste your inseeq data key (it stays hidden): ").strip()
    if not api_key:
        sys.exit("No key entered, so nothing was changed.")
    return api_key


def key_from_clipboard() -> str:
    copied = (read_clipboard() or "").strip()
    if not copied.startswith(KEY_PREFIX) or re.search(r"\s", copied):
        sys.exit("The clipboard does not hold an inseeq data key. Click Copy on the key page, then run this again. Nothing was changed.")
    return copied


def setup(flag: str = "") -> None:
    if flag not in ("", "--from-clipboard"):
        sys.exit("Usage: uv run cli.py setup --from-clipboard, or uv run cli.py setup to type the key")
    from_clipboard = flag == "--from-clipboard"
    api_key = key_from_clipboard() if from_clipboard else ask_for_key()

    api_url = os.environ.get("INSEEQ_API_URL") or DEFAULT_API_URL
    client = Client(api_key, api_url)
    try:
        status, tables = client.status(), client.list_tables()
    except InseeqError as error:
        sys.exit(f"The key did not connect. {error.code}: {error.message} Nothing was changed.")

    password = os.environ.get("DASHBOARD_PASSWORD") or secrets.token_urlsafe(24)
    save_env({"INSEEQ_API_KEY": api_key, "INSEEQ_API_URL": api_url, "DASHBOARD_PASSWORD": password})
    if from_clipboard:
        write_clipboard("")

    refreshed_at = status["refreshed_at"]
    print(f"Connected. {len(tables)} tables. Last refresh: {time_ago(refreshed_at) if refreshed_at else 'not yet'}.")
    print("Saved the key and a dashboard password in .env. Neither was printed.")
    print("Next: uv run uvicorn app.main:app --reload, open http://localhost:8000, and run uv run cli.py password to copy the password.")


def password() -> None:
    saved = os.environ.get("DASHBOARD_PASSWORD")
    if not saved:
        sys.exit("No DASHBOARD_PASSWORD in .env yet. Run uv run cli.py setup --from-clipboard first.")
    if not write_clipboard(saved):
        sys.exit("Could not reach the clipboard. The password is DASHBOARD_PASSWORD in .env.")
    print("Copied the dashboard password. Paste it on the login page.")


def vercel_env() -> None:
    """Copies the values a deployed dashboard needs from .env to the linked Vercel project, without printing them."""
    names = [name for name in VERCEL_NAMES if os.environ.get(name)]
    if "INSEEQ_API_KEY" not in names or "DASHBOARD_PASSWORD" not in names:
        sys.exit("No key or password in .env yet. Run uv run cli.py setup --from-clipboard first.")
    if not (ROOT / ".vercel" / "project.json").exists():
        sys.exit("Link the project first: npx vercel link")
    npx = shutil.which("npx")
    if not npx:
        sys.exit("npx was not found. Install Node.js from https://nodejs.org, then run this again.")
    for name in names:
        command = [npx, "vercel", "env", "add", name, "production", "--sensitive", "--force"]
        run = subprocess.run(command, check=False, input=os.environ[name], text=True, stdout=subprocess.DEVNULL, cwd=ROOT)
        if run.returncode != 0:
            sys.exit(f"Vercel refused {name}. Check npx vercel whoami, then run this again.")
        print(f"Set {name} on Vercel.")
    print("Next: npx vercel deploy --prod")


def default_params(sql: str) -> list[dict[str, str]] | None:
    """Fills the date parameters a saved query uses with the last 30 days, in the client's time zone."""
    names = sorted(set(PARAMETER.findall(sql)))
    if not names:
        return None
    period = get_period(DEFAULT_RANGE)
    defaults: dict[str, date] = {"start_date": period.start, "end_date": period.end, "day": period.end}
    unknown = [name for name in names if name not in defaults]
    if unknown:
        sys.exit(f"This query needs @{unknown[0]}, and only dates are filled in here. Run it from code with params.")
    print(f"Using {', '.join(f'@{name} = {defaults[name]}' for name in names)}.", file=sys.stderr)
    return [{"name": name, "type": "DATE", "value": defaults[name].isoformat()} for name in names]


def query(sql_or_name: str | None = None) -> None:
    if not sql_or_name:
        sys.exit('Usage: uv run cli.py query "select 1 as ok", or the name of a file in queries/')
    file = QUERIES_DIR / f"{sql_or_name}.sql"
    sql = file.read_text() if file.exists() else sql_or_name
    result = get_client().query(sql, params=default_params(sql), row_limit=QUERY_ROW_LIMIT)
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


COMMANDS = {"setup": setup, "password": password, "query": query, "webhook": webhook, "vercel-env": vercel_env}


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
