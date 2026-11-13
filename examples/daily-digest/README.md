# Daily Slack digest

Every morning at 07:00 UTC, GitHub Actions runs one query for yesterday and posts the answer to a Slack channel. No server.

It reads `GET /v1/status` first. If the newest build failed, or the data is more than 48 hours old, it posts "inseeq data is not fresh" instead, and the run fails. An API or Slack error also fails the run, with no post.

## Set it up

1. Move the workflow to where GitHub looks for it:

   ```bash
   mkdir -p .github/workflows
   git mv examples/daily-digest/daily-digest.yml .github/workflows/
   ```

2. On GitHub, open the repo's Settings, then Secrets and variables, then Actions. Add two repository secrets:
   - `INSEEQ_API_KEY`: your API key.
   - `SLACK_WEBHOOK_URL`: a webhook URL for the channel. In Slack, add the app "Incoming Webhooks" and pick the channel.
3. Change `queries/daily_digest.sql` to what you want each morning. It gets `@day`, yesterday in UTC, as a DATE. Each row becomes one line of `column: value` pairs, up to 20 lines, plus "and N more rows" when there are more. The default counts yesterday's leads by channel.
4. Push, open the Actions tab, pick Daily digest and press Run workflow. One post arrives.

To try it on your machine, add `SLACK_WEBHOOK_URL` to `.env` and run `uv run examples/daily-digest/digest.py` from the repo root.

## The rule

Post counts, never rows about people. A Slack channel has no login, and published tables can hold personal data. Group and count in the SQL, and select no names, emails or ids.
