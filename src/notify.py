"""Build notification payloads: summary.json (CI), whatsapp.txt (<900 chars), email.html."""
import json
from pathlib import Path
from datetime import datetime, timezone

DATA = Path("data")


def build_summary(all_rows: list, per_platform: dict, errors: list, sheet_result: dict) -> dict:
    ai = [h for h in all_rows if h.tech_stack == "AI"]
    bc = [h for h in all_rows if h.tech_stack == "Blockchain"]
    urgent = sorted(
        (h for h in all_rows
         if h.deadline_days is not None and 0 <= h.deadline_days <= 4),
        key=lambda h: (h.deadline_days, h.name),
    )
    seen, urgent_unique = set(), []
    for h in urgent:  # dual-track rows share a link — list each hackathon once
        if h.link not in seen:
            seen.add(h.link)
            urgent_unique.append(h)

    def _entry(h):
        return {"name": h.name, "platform": h.platform, "prize": h.prize_pool,
                "link": h.link, "track": h.tech_stack, "days": h.deadline_days}

    def _sort_key(h):
        return (h.deadline_days is None, h.deadline_days if h.deadline_days is not None else 0, h.name)

    by_platform = {}
    for plat in ["DoraHacks", "Devpost", "Devfolio"]:  # priority order
        rows = sorted((h for h in all_rows if h.platform == plat), key=_sort_key)
        by_platform[plat] = [_entry(h) for h in rows]
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "found_total": len(all_rows),
        "ai_count": len(ai),
        "blockchain_count": len(bc),
        "per_platform": per_platform,
        "errors": errors,
        "sheet": sheet_result,
        "sheet_new": sum(v.get("new", 0) for v in sheet_result.values()) if sheet_result else 0,
        "sheet_updated": sum(v.get("updated", 0) for v in sheet_result.values()) if sheet_result else 0,
        "urgent": [
            {"name": h.name, "platform": h.platform, "prize": h.prize_pool,
             "link": h.link, "track": h.tech_stack, "days": h.deadline_days}
            for h in urgent_unique
        ],
        "by_platform": by_platform,
        "top_new": [
            {"name": h.name, "platform": h.platform, "prize": h.prize_pool, "link": h.link, "track": h.tech_stack}
            for h in all_rows[:8]
        ],
    }


def write_artifacts(summary: dict, slot_label: str, sheet_url: str):
    DATA.mkdir(exist_ok=True)
    (DATA / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    new = summary.get("sheet_new", 0)
    upd = summary.get("sheet_updated", 0)
    tops = summary.get("top_new", [])[:3]
    top_str = "; ".join(f"{t['name'][:40]} ({t['platform']})" for t in tops) or "no matches"
    # ASCII-only: survives Windows consoles, curl urlencode, and CallMeBot
    marker = "OK" if not summary.get("errors") else "WARN"
    sheet_bit = f"sheet +{new} new ~{upd} updated" if summary.get("sheet") else "sheet skipped (dry-run)"
    wa = (
        f"[{marker}] Scout {slot_label}: "
        f"found {summary.get('found_total', 0)} (AI:{summary.get('ai_count',0)} BC:{summary.get('blockchain_count',0)}); "
        f"{sheet_bit}. Top: {top_str}. {sheet_url}"
    )
    (DATA / "whatsapp.txt").write_text(wa[:900], encoding="utf-8")

    urgent = summary.get("urgent", [])
    by_platform = summary.get("by_platform", {})

    th = ("<th style='border:1px solid #ccc;padding:6px;background:#f2f2f2;text-align:left;'>")
    td = "<td style='border:1px solid #ccc;padding:6px;'>"

    def _days_cell(d):
        return f"{td}{d} day{'s' if d != 1 else ''}</td>" if d is not None else f"{td}—</td>"

    def _table(rows, show_platform=False):
        head = (f"<table style='border-collapse:collapse;width:100%;font-size:14px;'>"
                f"<tr>{th}Hackathon</th>{th}Track</th>"
                + (f"{th}Platform</th>" if show_platform else "")
                + f"{th}Days Left</th>{th}Prize</th>{th}Link</th></tr>")
        body = "".join(
            f"<tr>{td}<b>{t['name']}</b></td>{td}{t['track']}</td>"
            + (f"{td}{t['platform']}</td>" if show_platform else "")
            + f"{_days_cell(t.get('days'))}{td}{t['prize']}</td>"
            f"{td}<a href='{t['link']}'>Open</a></td></tr>"
            for t in rows
        )
        return head + body + "</table>"

    if urgent:
        urgent_html = (f"<h3 style='color:#b3261e;'>Closing in the next 0-4 days ({len(urgent)})</h3>"
                       + _table(urgent, show_platform=True))
    else:
        urgent_html = ("<h3>Closing in the next 0-4 days (0)</h3>"
                       "<p>Nothing urgent — all deadlines are 5+ days out.</p>")

    html = f"""<h2>Hackathon Scout – {slot_label}</h2>
{urgent_html}
<p>Full sheet (all hackathons by platform, soonest first): <a href='{sheet_url}'>Open Google Sheet</a></p>"""
    (DATA / "email.html").write_text(html, encoding="utf-8")
    return summary
