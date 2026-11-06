# inseeq Python starter

A small FastAPI app on the [inseeq Data API](https://api.inseeq.com/llms.txt): a password login, a dashboard of your data's freshness and tables, a signed webhook receiver and a client. It works for any organization. Change it or replace it.

## Start

Make a private copy, because it will hold your dashboards. A fork of a public repo stays public.

```bash
gh repo create my-dashboard --template inseeq/python-starter --private --clone
cd my-dashboard
uv run cli.py setup
uv run uvicorn app.main:app --reload
```

You need [uv](https://docs.astral.sh/uv/). In Claude, with the inseeq connector, ask for a data key and open the one-time link. `setup` asks for the key in your own terminal, writes `.env`, prints your dashboard password once and checks the connection. Then open <http://localhost:8000>, and open Claude in this folder to build.

## What is here

| Path | What it does |
|---|---|
| `app/inseeq.py` | The API client: paging, retries and typed errors |
| `app/main.py`, `app/session.py` | The routes, the login gate, the webhook receiver and the signed cookie. Add your work to `handle_event` |
| `app/pages.py` | The HTML. Every value goes through `escape` |
| `queries/` | One `.sql` file per metric, with one SELECT each |
| `cli.py` | The commands below |

```python
client = get_client()
tables = client.list_tables()
result = client.run_saved(
    "since_example",
    params=[{"name": "since", "type": "DATE", "value": "2026-01-01"}],
)
```

The client is synchronous, so call it from plain `def` routes.

## Commands

```bash
uv run cli.py query "select 1 as ok"   # SQL, or the name of a file in queries/
uv run cli.py webhook register https://your-app.example.com
uv run cli.py webhook test <id>
```

`webhook register` writes `INSEEQ_WEBHOOK_SECRET` to `.env`. The app reads `.env` only when it starts, and `--reload` does not watch it, so restart it. Until then it answers 503 to every delivery.

The receiver checks each delivery's signature and logs the event. Deliveries can repeat, so make your work safe to repeat, or keep each `webhook-id` in shared storage for 4 days.

## Deploy

Any host that runs Python works: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Keep the repo private. Set `INSEEQ_API_KEY` and `DASHBOARD_PASSWORD`, plus `INSEEQ_WEBHOOK_SECRET` for webhooks. The app will not start without the password. Serve it over https: the session cookie is `Secure` everywhere except localhost. Webhooks need a public https URL on port 443.

## Learn more

- [Data API docs](https://api.inseeq.com/llms.txt)
- [Dashboards](https://api.inseeq.com/docs/dashboards.md)
- [Automations](https://api.inseeq.com/docs/automations.md)
