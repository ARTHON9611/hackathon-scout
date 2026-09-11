"""Devpost — L1: official-ish JSON API, L2: none (API is stable since 2023)."""
import re
from concurrent.futures import ThreadPoolExecutor
from .base import session, get, polite
from ..models import Hackathon
from ..filter import classify, is_eligible

API = "https://devpost.com/api/hackathons"
PLATFORM = "Devpost"


def _clean_prize(html: str) -> str:
    if not html:
        return "Not specified"
    text = re.sub(r"<[^>]+>", "", html).strip()
    text = re.sub(r"\s+", " ", text)
    return text or "Not specified"


def _days_left(item: dict) -> int | None:
    """Parse '20 days left' / 'about 1 month left' / fallback to end date of
    'Jul 31 - Oct 01, 2026'. Returns int days or None."""
    s = (item.get("time_left_to_submission") or "").lower()
    m = re.search(r"(\d+)\s*hour", s)
    if m:
        return 0
    m = re.search(r"(\d+)\s*day", s)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*week", s)
    if m:
        return int(m.group(1)) * 7
    m = re.search(r"(\d+)\s*month", s)
    if m:
        return int(m.group(1)) * 30
    # fallback: end date in "Jul 31 - Oct 01, 2026"
    dates = (item.get("submission_period_dates") or "")
    m = re.search(r"-\s*([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})", dates)
    if m:
        try:
            from dateutil import parser as _dp
            from datetime import datetime, timezone
            end = _dp.parse(m.group(1))
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            return max(0, (end - datetime.now(timezone.utc)).days)
        except Exception:
            return None
    return None


def _status(item: dict) -> str:
    state = (item.get("open_state") or "").lower()  # open | upcoming | ended
    if state == "open":
        return "Open"
    if state == "upcoming":
        return "Upcoming"
    if state in ("ended", "closed"):
        return "Closed"
    # fallback to human string
    return item.get("time_left_to_submission") or state or "Open"


def fetch_page(page: int, timeout: int = 20) -> list:
    s = session()
    # status[]=open & status[]=upcoming keeps payload small and relevant
    params = [("status[]", "open"), ("status[]", "upcoming"), ("page", page)]
    r = get(s, API, timeout=timeout, params=params)
    return r.json().get("hackathons", [])


def parse(item: dict) -> list:
    """One Devpost item -> 0..2 Hackathon rows (dual-track possible)."""
    status = _status(item)
    if not is_eligible(status):
        return []
    themes = " ".join(t.get("name", "") for t in item.get("themes", []))
    title = item.get("title", "").strip()
    tracks = classify(themes, title, "")
    if not tracks:
        return []
    prize = _clean_prize(item.get("prize_amount", ""))
    link = (item.get("url") or "").strip()
    if not link or not title:
        return []
    if item.get("time_left_to_submission"):
        status_detail = item["time_left_to_submission"].strip()
        status = f"Open ({status_detail})" if status == "Open" else status
        # normalize back to Open/Upcoming for sheet consistency
        status = "Open" if status.startswith("Open") else status
    days = _days_left(item)
    return [
        Hackathon(name=title, platform=PLATFORM, tech_stack=t, status=status,
                  prize_pool=prize, link=link, deadline_days=days)
        for t in sorted(tracks)
    ]


def scrape(max_pages: int = 6, timeout: int = 20, delay: float = 1.0) -> tuple:
    """Returns (items, error_or_None). Never raises — failure isolation."""
    out = []
    try:
        for p in range(1, max_pages + 1):
            polite(delay if p > 1 else 0)
            items = fetch_page(p, timeout)
            if not items:
                break
            for it in items:
                try:
                    out.extend(parse(it))
                except Exception:
                    continue
        return out, None
    except Exception as e:
        return out, f"Devpost: {e}"
