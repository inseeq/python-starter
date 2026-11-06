# AGENTS.md

A FastAPI app on the inseeq Data API. Read <https://api.inseeq.com/llms.txt> before any data work.

- Never read, print or copy `.env`, including through a shell. `cli.py` loads it itself, and a script of yours can call `load_env()` from `app.inseeq`.
- `uv run cli.py setup` needs the user's own terminal. Never run it for them, and never ask for a key or password in chat.
- To check a logged-in page, start your own server with a throwaway `DASHBOARD_PASSWORD` on the command line.
- The key stays on the server. Never send it to a page or add a route that returns it.
- Pass values through `params`. Never build SQL strings.
- Never render data as raw HTML: pass every value through `html.escape`.
- Tables can hold personal data. Keep rows out of logs, commits and fixtures.
- New routes stay behind the login. Add to `PUBLIC_PATHS` only if the user asks for a public route.
- Check `truncated` before you trust a total.
- Webhook deliveries can repeat. Keep work in `handle_event` safe to repeat.
