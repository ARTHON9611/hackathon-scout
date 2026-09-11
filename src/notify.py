"""Build notification payloads: summary.json (CI), whatsapp.txt (<900 chars), email.html."""
import json
from pathlib import Path
from datetime import datetime, timezone

DATA = Path("data")


def build_summary(all_rows: list, per_platform: dict, errors: list, sheet_result: dict) -> dict:
    ai = [h for h in all_rows if h.tech_stack == "AI"]
    bc = [h for h in all_rows if h.tech_stack == "Blockchain"]
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

    rows = "".join(
        f"<li><b>{t['name']}</b> [{t['track']}/{t['platform']}] {t['prize']} – "
        f"<a href='{t['link']}'>{t['link']}</a></li>"
        for t in summary.get("top_new", [])
    )
    html = f"""<h2>Hackathon Scout – {slot_label}</h2>
<p>Found: {summary['found_total']} (AI {summary['ai_count']}, Blockchain {summary['blockchain_count']}) |
Sheet: +{new} new, ~{upd} updated</p>
<p>Per platform: {json.dumps(summary.get('per_platform', {}))}</p>
<p>Errors: {summary.get('errors') or 'none'}</p>
<ul>{rows or '<li>No new matches this run.</li>'}</ul>
<p>Sheet: <a href='{sheet_url}'>{sheet_url}</a></p>"""
    (DATA / "email.html").write_text(html, encoding="utf-8")
    return summary
