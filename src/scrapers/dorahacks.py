"""DoraHacks — PRIORITY scraper, 3 layers for lifelong stability.

L1 (primary): official prod JSON API (reverse-engineered from the Nuxt bundle):
    GET https://dorahacks.io/api/v1/hub/hackathons?page=N&pageSize=100
    -> {count, results: [{id, uname, title, tags, ecosystem,
        timeline_pre_register/start/end (unix), bonus_price/token, ...}]}
    Status computed locally from timelines vs now. Polite: 1 session,
    pageSize=100, 2s between pages, browser-like headers (AWS WAF throttles
    aggressive probing — keep total run under ~10 list requests).

L2: detail-page JSON-LD parse for DORAHACKS_SEED_URLS (covers API gaps).
L3: Playwright list harvest (optional, only if installed).

No login needed anywhere.
"""
import os
import re
import time
from urllib.parse import urljoin
from .base import session, polite
from ..models import Hackathon
from ..filter import classify, is_eligible

PLATFORM = "DoraHacks"
BASE = "https://dorahacks.io"
API = "https://dorahacks.io/api/v1/hub/hackathons"

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://dorahacks.io",
    "Referer": "https://dorahacks.io/hackathon",
}

# Staging fixtures pollute the API ("Test-Frontier-*" with tags like "ai").
# They are never real public hackathons — drop them explicitly.
_TEST_TITLE = re.compile(r"^test[\s\-_]", re.I)


def _status_from_timelines(pre: int, start: int, end: int, now: int) -> str:
    eff_start = pre or start
    if eff_start and now < eff_start:
        return "Upcoming"
    if end and now < end:
        return "Open"
    if end and now >= end:
        return "Closed"
    return "Open"  # no usable timeline -> keep (site lists it as live)


def _prize(item: dict) -> str:
    price, token = item.get("bonus_price"), (item.get("bonus_token") or "").strip()
    try:
        price = float(price)
    except (TypeError, ValueError):
        return "Not specified"
    if price <= 0:
        return "Not specified"
    amt = str(int(price)) if price == int(price) else str(price)
    return f"{amt} {token}".strip() or "Not specified"


def _link(item: dict) -> str:
    slug = item.get("uname") or item.get("id")
    return f"{BASE}/hackathon/{slug}"


def parse_api_item(item: dict, now: int) -> list:
    title = (item.get("title") or "").strip()
    if not title or _TEST_TITLE.match(title):
        return []
    status = _status_from_timelines(
        int(item.get("timeline_pre_register") or 0),
        int(item.get("timeline_start") or 0),
        int(item.get("timeline_end") or 0),
        now,
    )
    if not is_eligible(status):
        return []
    tag_blob = " ".join([
        str(item.get("tags") or ""),
        str(item.get("ecosystem") or ""),
    ])
    tracks = classify(tag_blob, title, "")
    if not tracks:
        return []
    link = _link(item)
    if "/hackathon/None" in link:
        return []
    prize = _prize(item)
    return [
        Hackathon(name=title, platform=PLATFORM, tech_stack=t, status=status, prize_pool=prize, link=link)
        for t in sorted(tracks)
    ]


def _fetch_api_page(s, page: int, page_size: int, timeout: int):
    r = s.get(API, params={"page": page, "pageSize": page_size}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def scrape_api(timeout: int = 25, page_size: int = 100, max_pages: int = 10, delay: float = 2.0) -> tuple:
    """Returns (rows, error_or_None). Single polite session."""
    from tenacity import retry, stop_after_attempt, wait_exponential
    s = session()
    s.headers.update(API_HEADERS)
    out, now = [], int(time.time())
    try:
        first = _fetch_api_page(s, 1, page_size, timeout)
    except Exception as e:
        return [], f"DoraHacks API unreachable: {e}"
    total = first.get("count") or 0
    pages = min(max_pages, max(1, (total + page_size - 1) // page_size))
    batch = [first] + [None] * (pages - 1)
    for p in range(2, pages + 1):
        polite(delay)
        try:
            batch[p - 1] = _fetch_api_page(s, p, page_size, timeout)
        except Exception as e:
            return out, f"DoraHacks API page {p} failed ({e}); kept {len(out)} rows"
    for data in batch:
        for item in (data or {}).get("results", []):
            try:
                out.extend(parse_api_item(item, now))
            except Exception:
                continue
    # dedupe by link+track
    seen, deduped = set(), []
    for h in out:
        k = (h.link, h.tech_stack)
        if k not in seen:
            seen.add(k)
            deduped.append(h)
    return deduped, None


def _normalize_base(url: str) -> str:
    m = re.match(r"(https?://dorahacks\.io/hackathon/[^/?#]+)", url)
    if m:
        return m.group(1).rstrip("/")
    return url.split("?")[0].split("#")[0].rstrip("/")


def _seed_details(timeout=20, delay=1.0) -> list:
    """L2: parse seed detail pages (JSON-LD) — fills gaps if API misses any."""
    from bs4 import BeautifulSoup
    import json as _json
    seeds = [u.strip() for u in os.getenv("DORAHACKS_SEED_URLS", "").split(",") if u.strip()]
    if not seeds:
        return []
    s = session()
    out = []
    for url in seeds[:10]:
        try:
            polite(delay)
            base = _normalize_base(url)
            r = s.get(base + "/detail", timeout=timeout)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text(" ", strip=True)
            name = ""
            for tag in soup.select('script[type="application/ld+json"]'):
                try:
                    data = _json.loads(tag.string or "{}")
                    if isinstance(data, dict) and data.get("@type") == "Event" and data.get("name"):
                        name = data["name"].strip()
                        break
                except Exception:
                    continue
            if not name:
                continue
            m = re.search(r"Hackathon Tags(.{0,400})", text)
            tags = m.group(1) if m else ""
            pm = re.search(r"Prize Pool\s+(.+?)\s+(Prize Pool|event timeline)", text, re.S)
            prize = re.sub(r"\s+", " ", pm.group(1)).strip()[:120] if pm else "Not specified"
            low = text.lower()
            status = "Upcoming" if "upcoming" in low else "Open"
            if "submission period ended" in low:
                status = "Closed"
            if not is_eligible(status):
                continue
            tracks = classify(tags, name, text[:4000])
            out.extend(
                Hackathon(name=name, platform=PLATFORM, tech_stack=t, status=status, prize_pool=prize, link=base)
                for t in sorted(tracks)
            )
        except Exception:
            continue
    return out


def scrape(max_details: int = 40, timeout: int = 25, delay: float = 2.0) -> tuple:
    out, err = scrape_api(timeout=timeout, delay=delay)
    # L2 seeds merge (dedupe by link+track)
    try:
        seeds = _seed_details(timeout=timeout)
        seen = {(h.link, h.tech_stack) for h in out}
        for h in seeds:
            if (h.link, h.tech_stack) not in seen:
                seen.add((h.link, h.tech_stack))
                out.append(h)
    except Exception:
        pass
    if not out and err:
        return [], err
    return out, err
