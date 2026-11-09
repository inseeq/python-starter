# inseeq Python starter

A private dashboard on your company's inseeq data, in a small FastAPI app: a paid media page to start, and Claude builds the rest with you.

## Start in Claude Code

You need:

- [Claude Code](https://claude.com/claude-code), in the desktop app or the terminal. A chat on claude.ai cannot make the project.
- The inseeq connector, added in Claude under Settings, Connectors.
- [uv](https://docs.astral.sh/uv/), which runs Python for you.

Open Claude Code in an empty folder and say:

```
Set up my inseeq dashboard from https://github.com/inseeq/python-starter
```

Claude does the rest. You do two things:

1. Open the key link Claude gives you, click **Show my key**, then **Copy**, and tell Claude "copied".
2. Log in to the dashboard Claude starts. Claude puts the password on your clipboard.

You get a paid media page on your own numbers from the last 30 days: spend, clicks, cost per click and click rate, spend per day and a table by platform. Then ask for more, for example: "Add a page for demos, by sales rep."

## For Claude: set it up

Do these steps in order. Say in one line what you are doing at each step.

1. **Make the user's own copy.** It will hold their dashboards, so it is private and theirs.
   - If `gh auth status` succeeds: `gh repo create <name> --template inseeq/python-starter --private --clone`, then `cd <name>`. Ask the user for a name, or use `inseeq-dashboard`.
   - If not: `git clone --depth 1 https://github.com/inseeq/python-starter <name> && cd <name> && rm -rf .git && git init -q`. Tell the user it lives only on their computer for now.
   - Never fork: a fork of a public repo stays public.
2. **Install:** `uv sync`. If `uv` is not found, tell the user to install it from <https://docs.astral.sh/uv/>, then restart Claude Code.
3. **Get a data key.** Call the inseeq connector's `create_data_key` with label `Dashboard`. Give the user the link exactly as it comes back, and say: "Open this, click Show my key, then Copy, and tell me when you've copied it." Never open the link, and never ask for the key in chat. If no inseeq tools are loaded, ask the user to add the inseeq connector in Claude, then restart Claude Code.
4. **When the user says they copied it:** `uv run cli.py setup --from-clipboard`. It checks the connection, then saves the key and a dashboard password in `.env`, clears the clipboard and prints neither. If it says the clipboard holds no key, ask the user to click Copy again.
5. **Start it:** `uv run uvicorn app.main:app --reload` in the background. If `lsof -iTCP:8000 -sTCP:LISTEN` shows port 8000 is taken, add `--port 8001` and use that address. Wait for it to answer, then run `uv run cli.py password` and tell the user: "Open http://localhost:8000 and paste the password. It's on your clipboard."
6. **Tell the user what they are looking at** in two or three sentences, then explain saved queries (below) in plain words, and offer to build their next page.

If the page shows "This page needs data your organization does not have yet", no ad platform is connected in inseeq yet.

## How it is built

| Path | What it holds |
|---|---|
| `app/paid_media.py` | The paid media page |
| `queries/` | Saved queries: one `.sql` file per question |
| `app/pages.py`, `app/charts.py` | The frame, headline numbers, cards, tables and the column chart. HTML drawn on the server, with every value escaped. No chart library, no script |
| `app/style.css` | Colors and sizes, light and dark |
| `app/data.py` | The date range, in your company's time zone, and `run_query` |
| `app/format.py` | Money, counts, percents and dates for people |
| `app/inseeq.py` | The API client: paging, retries and clear errors |
| `app/main.py`, `app/session.py` | The routes, the password login and the webhook receiver. Add your work to `handle_event` |
| `examples/daily-digest` | A daily Slack message from one query, run by GitHub Actions |
| `cli.py` | The commands below |

### Saved queries

A saved query is a file in `queries/` that holds one SELECT, for example `queries/paid_media_daily.sql`:

```sql
select date_native as day, platform, sum(spend_amount) as spend, sum(impressions) as impressions, sum(clicks) as clicks
from int_ads__performance_daily
where not is_detail and date_native between @start_date and @end_date
group by day, platform
order by day, platform
```

- **Tables are named without a dataset.** The data key already decides whose data you read.
- **`@start_date` is a parameter.** The value travels separately from the SQL, so it is never pasted into it.
- **A page runs it by name:**

  ```python
  period = get_period("30d")
  rows = run_query("paid_media_daily", date_params(period.start, period.end))["rows"]
  ```

  `run_query` calls `client.run_saved` and refuses a cut-off answer (`truncated`), so a total is never silently short.
- **Run one from the terminal** to see its rows: `uv run cli.py query paid_media_daily`. It fills `@start_date` and `@end_date` with the last 30 days. This also takes plain SQL: `uv run cli.py query "select 1 as ok"`.
- **Answers are cached until the next refresh.** inseeq rebuilds your data several times a day, and the same query with the same values comes back from the cache until then. "Updated 2 hours ago" at the top of the page is the time of the last rebuild.

To build a new page, ask Claude. It finds the right table with the inseeq connector, writes the query, and adds the page, following `AGENTS.md`.

## Put it online

The dashboard runs on [Vercel](https://vercel.com), on its free plan. Vercel finds `app` in `app/main.py` by itself. Ask Claude to "put my dashboard online", or:

```bash
npx vercel link --yes      # sign in if asked, and create a project for this folder
uv run cli.py vercel-env   # copies the key and the password from .env to Vercel, without printing them
npx vercel deploy --prod
```

Anyone with the address and the password can see the dashboard. To change the password, edit `DASHBOARD_PASSWORD` in `.env` and run `uv run cli.py vercel-env` again. `.vercelignore` keeps `.env` out of the upload.

Webhooks need the deployed https address: `uv run cli.py webhook register https://<your-app>.vercel.app`, then `uv run cli.py vercel-env` and deploy again.

Other Python hosts work too: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, with `INSEEQ_API_KEY` and `DASHBOARD_PASSWORD` set.

## Commands

| Command | What it does |
|---|---|
| `uv run uvicorn app.main:app --reload` | The dashboard on http://localhost:8000 |
| `uv run cli.py setup --from-clipboard` | Saves a copied data key to `.env`. `uv run cli.py setup` alone asks for it instead |
| `uv run cli.py password` | Copies the dashboard password |
| `uv run cli.py query <name or SQL>` | Runs a saved query, or SQL, and prints the rows |
| `uv run cli.py vercel-env` | Sends `.env`'s values to the linked Vercel project |
| `uv run cli.py webhook register <url>` | Asks inseeq to send events to your deployed dashboard |
| `uv run cli.py webhook test <id>` | Sends a test event |

The app reads `.env` only when it starts, and `--reload` does not watch it, so restart it after `webhook register`. Until then it answers 503 to every delivery. Deliveries can repeat, so make your work in `handle_event` safe to repeat.

## Learn more

- [Data API docs](https://api.inseeq.com/llms.txt)
- [Dashboards](https://api.inseeq.com/docs/dashboards.md)
- [Automations](https://api.inseeq.com/docs/automations.md)
