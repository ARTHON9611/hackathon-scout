"""Sheets upsert — Link is PK. Auto-creates tabs. Batch ops. Never deletes rows."""
import os
import gspread
from google.oauth2.service_account import Credentials

HEADER = ["Hackathon Name", "Platform", "Tech Stack", "Status", "Prize Pool", "Link", "Last_Updated"]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]


def _client():
    import json
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    if raw:
        info = json.loads(raw)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(path, scopes=SCOPES)
    return gspread.authorize(creds)


def _ensure_ws(sh, title: str):
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=len(HEADER))
        ws.update("A1:G1", [HEADER])
        return ws
    vals = ws.get_all_values()
    if not vals:
        ws.update("A1:G1", [HEADER])
    elif vals[0] != HEADER:
        ws.update("A1:G1", [HEADER])
    return ws


def upsert(rows_by_tab: dict, spreadsheet_id: str) -> dict:
    """rows_by_tab: {'AI': [Hackathon], 'Blockchain': [Hackathon]} -> {'AI': {new, updated}, ...}"""
    gc = _client()
    sh = gc.open_by_key(spreadsheet_id)
    result = {}
    for tab, rows in rows_by_tab.items():
        ws = _ensure_ws(sh, tab)
        existing = ws.get_all_records()
        link_to_row = {}
        for i, rec in enumerate(existing, start=2):  # 1-indexed + header
            link = str(rec.get("Link", "")).strip().rstrip("/")
            if link:
                link_to_row[link] = i
        new, updated = 0, 0
        appends = []
        for h in rows:
            key = h.link
            if key in link_to_row:
                r = link_to_row[key]
                # update Status (D), Prize (E), Last_Updated (G); keep name/platform fresh too
                ws.batch_update([
                    {"range": f"A{r}:G{r}", "values": [h.row()]}
                ])
                updated += 1
            else:
                appends.append(h.row())
                link_to_row[key] = True
                new += 1
        if appends:
            ws.append_rows(appends, value_input_option="USER_ENTERED")
        result[tab] = {"new": new, "updated": updated, "total": len(existing) + new}
    # _Meta health tab
    try:
        meta = _ensure_ws(sh, "_Meta")
        from datetime import datetime, timezone
        meta.append_row([datetime.now(timezone.utc).isoformat(), str(result)])
    except Exception:
        pass
    return result
