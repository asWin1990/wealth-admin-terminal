# AURA BI Terminal

Market-intelligence terminal for a mutual fund distributor desk (Streamlit).
A scheduled GitHub Action fetches data into `data/`; the Streamlit app only **reads** it.

## Deploy (new link)
1. Create a new GitHub repo and upload all files in this folder (keep the `.github` and `.streamlit` folders).
2. In **Settings > Secrets and variables > Actions** add `GEMINI_API_KEY` (optional: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `RECIPIENT_EMAIL`, `WHATSAPP_PHONE`, `CALLMEBOT_API_KEY`, `DASHBOARD_URL`).
3. **Actions > Refresh market data > Run workflow** once, so `data/market_snapshot.json` and `data/history.jsonl` exist.
4. On share.streamlit.io choose **Create app**, pick the repo, main file `app.py`. That gives the new URL.
5. Optional: in the Streamlit app's Secrets add `ADMIN_PASSWORD = "..."` to unlock an admin-only refresh button.

## Keep these honest
- `config.yaml > macro_manual` (repo rate, G-Sec yields, CPI/WPI, 10Y averages) and `amfi_monthly_manual` are typed in by hand. Update them after each RBI/CPI/AMFI release and set `manual_data_asof`. The header shows a warning chip when this date is missing or older than 35 days.
- If the NSE flows endpoint blocks the runner, flows fall back to the config values and are labelled MANUAL.
- History (sparklines, FPI/DII chart, sell-streak, P/E percentile after 30 sessions) builds from `data/history.jsonl`, one row per session.

## Compliance
Labels are neutral (Favourable / Neutral / Cautious) and the exported brief and client note drafts carry a standing disclaimer. Review client-facing text with your compliance process before sending.
