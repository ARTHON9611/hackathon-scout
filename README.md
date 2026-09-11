# Hackathon Scout 🏴‍☠️

Automated AI + Blockchain hackathon tracker: scrapes **Devpost, DoraHacks (priority), Devfolio** twice daily and upserts to Google Sheets (`AI | Blockchain | _Meta` tabs). Alerts via **email on every run (summary) + on failure**. (WhatsApp/Telegram can be added later.)

## One-time setup (15 min)

1. **Google Sheet**
   - Create a Sheet, copy its ID from URL (`/d/<ID>/edit`).
   - GCP Console → enable **Sheets API + Drive API** → Credentials → **Service Account** → JSON key.
   - Share the Sheet with the service account `client_email` (Editor).
2. **GitHub Secrets** (repo → Settings → Secrets → Actions):
   - `SPREADSHEET_ID`
   - `GCP_SERVICE_ACCOUNT_JSON` (full JSON content)
   - `DORAHACKS_SEED_URLS` (optional, comma-separated fallback URLs)
   - `MAIL_USERNAME` (gmail), `MAIL_PASSWORD` (**App Password**: Google → Security → 2-Step → App passwords), `MAIL_TO`
3. Push → Actions → `scout.yml` runs `30 3,13 * * *` (9AM/7PM IST) + manual dispatch.

## Local run

```bash
pip install -r requirements.txt
copy .env.example .env   # fill SPREADSHEET_ID etc.
set DRY_RUN=true         # powershell: $env:DRY_RUN="true"
python -m src.main       # writes data/ + data/whatsapp.txt + data/email.html, no Sheet write
python -m pytest -q
```

## How it survives for years

- **Layered scrapers**: Devpost JSON API → DoraHacks JSON-LD/detail → Playwright list fallback. One layer breaking ≠ total failure.
- **Failure isolation**: each platform in try/except; partial push always happens.
- **Link as PK**: upsert by normalized URL; Closed rows kept, never deleted.
- **Forensics**: `data/raw_*.json` + `_Meta` tab + auto-GitHub-Issue on failure.
- **Pinned**: `ubuntu-22.04`, `python 3.11`, pinned `requirements.txt`, Dependabot weekly.
- **Polite**: 1s delay, 5 workers, retries with backoff.

## If DoraHacks list page changes

Add sniffed XHR to `src/config.yaml:dorahacks.api_candidates`, or drop 2-3 live URLs into `DORAHACKS_SEED_URLS` secret — no code deploy needed for coverage.
