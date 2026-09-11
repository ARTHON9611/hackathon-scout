"""Orchestrator: scrape (isolated) -> dedupe -> push (or dry-run) -> summaries.

Env:
  SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_JSON / GOOGLE_SERVICE_ACCOUNT_FILE,
  DRY_RUN=true to skip Sheets, SLOT_LABEL for notifications.
Exit 0 on partial success; exit 1 only if ALL scrapers failed.
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scrapers import devpost, dorahacks, devfolio  # noqa: E402
from src.sheets import upsert  # noqa: E402
from src.notify import build_summary, write_artifacts  # noqa: E402

DATA = Path("data")


def dedupe(rows):
    seen, out = set(), []
    for h in rows:
        k = (h.link, h.tech_stack)
        if k not in seen:
            seen.add(k)
            out.append(h)
    return out


def main():
    DATA.mkdir(exist_ok=True)
    all_rows, per_platform, errors = [], {}, []

    for name, fn in [
        ("DoraHacks", lambda: dorahacks.scrape(max_details=40)),
        ("Devpost", lambda: devpost.scrape(max_pages=6)),
        ("Devfolio", lambda: devfolio.scrape()),
    ]:
        try:
            rows, err = fn()
            rows = dedupe(rows)
            all_rows.extend(rows)
            per_platform[name] = len(rows)
            # raw snapshot for forensics (lifelong debugging)
            (DATA / f"raw_{name.lower()}.json").write_text(
                json.dumps([r.model_dump() for r in rows], indent=2), encoding="utf-8"
            )
            if err:
                errors.append(err)
            print(f"[{name}] {len(rows)} rows. {err or 'ok'}", flush=True)
        except Exception as e:  # absolute isolation
            errors.append(f"{name}: {e}")
            per_platform[name] = 0
            print(f"[{name}] CRASH: {e}", flush=True)

    all_rows = dedupe(all_rows)
    print(f"TOTAL: {len(all_rows)} | errors={errors}", flush=True)

    sheet_result = {}
    dry = os.getenv("DRY_RUN", "false").lower() == "true"
    sheet_id = os.getenv("SPREADSHEET_ID", "")
    if not dry and sheet_id:
        ai = [h for h in all_rows if h.tech_stack == "AI"]
        bc = [h for h in all_rows if h.tech_stack == "Blockchain"]
        try:
            sheet_result = upsert({"AI": ai, "Blockchain": bc}, sheet_id)
            print(f"SHEET: {sheet_result}", flush=True)
        except Exception as e:
            errors.append(f"Sheets: {e}")
            print(f"SHEETS CRASH: {e}", flush=True)
    else:
        print("DRY-RUN or no SPREADSHEET_ID — skipping Sheets push.", flush=True)
        (DATA / "dryrun_rows.json").write_text(
            json.dumps([r.model_dump() for r in all_rows], indent=2), encoding="utf-8"
        )

    slot = os.getenv("SLOT_LABEL", datetime.now(timezone.utc).strftime("%d %b %H:%M UTC"))
    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}" if sheet_id else "(no sheet configured)"
    summary = build_summary(all_rows, per_platform, errors, sheet_result)
    write_artifacts(summary, slot, sheet_url)
    print(json.dumps(summary, indent=2)[:2000], flush=True)

    if len(all_rows) == 0 and len(errors) >= 3:
        print("ALL scrapers failed.", flush=True)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
