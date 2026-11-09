# AGENTS.md

A FastAPI app on the inseeq Data API. To set it up for a user, follow "For Claude: set it up" in `README.md`. Read <https://api.inseeq.com/llms.txt> before any data work.

- Never read, print or copy `.env`, including through a shell. `cli.py` loads it itself, and a script of yours can call `load_env()` from `app.inseeq`.
- Never ask for a key or a password in chat. Set up a key with `uv run cli.py setup --from-clipboard`, after the user says they copied it from the key page. Hand over the dashboard password with `uv run cli.py password`, which copies it. Never print either, and never read the clipboard yourself.
- To check a logged-in page, start your own server with a throwaway `DASHBOARD_PASSWORD` on the command line, bound to `127.0.0.1`.
- The key stays on the server. Never send it to a page or add a route that returns it.
- Pass values through `params`. Never build SQL strings.
- Never render data as raw HTML: pass every value through `html.escape`, or build it with the helpers in `app/pages.py`, which escape for you. Colors go in as the classes in `app/charts.py`. Never put data in a `style` attribute.
- Tables can hold personal data. Keep rows out of logs, commits and fixtures.
- New routes stay behind the login. Add to `PUBLIC_PATHS` only if the user asks for a public route.
- Check `truncated` before you trust a total. `run_query` in `app/data.py` refuses a cut-off answer.
- Webhook deliveries can repeat. Keep work in `handle_event` safe to repeat.

## Pages

- A page is a module like `app/paid_media.py` plus one route in `app/main.py`. The route is a plain `def`, because the client is synchronous.
- Put each query in `queries/`, and read it with `run_query` and `date_params` from `app/data.py`. `get_period` gives the chosen range in the client's days.
- Build from `app/pages.py` (`frame`, `page_header`, `kpi_row`, `card`, `data_table`, `numbers`, `empty_state`, `error_state`) and `column_chart` in `app/charts.py`. Colors are tokens in `app/style.css`. Never write a hex value anywhere else.

## How a page reads

- Lead with the numbers for the period, compared with the period before. The chart comes after.
- Write dates for people: "Nov 8", "Oct 10 to Nov 8, 2026", "Updated 2 hours ago". Never show a raw timestamp, a time zone name, a table name or a column name on a page. `app/format.py` has the helpers.
- Name things in business words: "Meta Ads", not `meta_ads`; "Booked a demo", not `is_demo_booked`.
- Use the client's day: `get_period` takes it from `cfg_client`. Never "yesterday" on the server's clock.
- One chart per question, one y-axis per chart. Give each entity one color and keep it on every page.
- Every chart has its numbers under "Show the numbers". Every page has an empty state that says what is missing, and a state for data the organization does not have.
- Look at the page in a browser, at desktop and phone width, before you call it done.
