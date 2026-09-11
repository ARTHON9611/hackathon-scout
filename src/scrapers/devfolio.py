"""Devfolio — L1: SSR HTML cards (themes + status visible, no auth)."""
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import session, get, polite
from ..models import Hackathon
from ..filter import classify, is_eligible

PLATFORM = "Devfolio"
LIST = "https://devfolio.co/hackathons"


def parse_card(card, soup_text="") -> list:
    a = card.select_one("a[href*='devfolio.co']")
    title_el = card.select_one("h3, h2, h4")
    title = title_el.get_text(strip=True) if title_el else ""
    link = ""
    if a and a.get("href"):
        link = a["href"].strip()
    if link.startswith("/"):
        link = urljoin("https://devfolio.co", link)
    blob = card.get_text(" ", strip=True)
    # theme + status cues
    m_theme = re.search(r"Theme\s+(.+?)(Open|Upcoming|Ended|Live|Apply now|Remind me|$)", blob)
    themes = m_theme.group(1).strip() if m_theme else ""
    low = blob.lower()
    if "ended" in low:
        status = "Closed"
    elif "upcoming" in low or "remind me" in low or "opens" in low:
        status = "Upcoming"
    elif "open" in low or "live" in low or "apply now" in low or "starts" in low:
        status = "Open"
    else:
        status = "Open"
    if not title or not link or not is_eligible(status):
        return []
    tracks = classify(themes, title, blob[:2000])
    if not tracks:
        return []
    return [
        Hackathon(name=title, platform=PLATFORM, tech_stack=t, status=status,
                  prize_pool="Not specified", link=link)
        for t in sorted(tracks)
    ]


def scrape(timeout: int = 20, delay: float = 1.0) -> tuple:
    out = []
    try:
        s = session()
        polite(0)
        r = get(s, LIST, timeout=timeout)
        soup = BeautifulSoup(r.text, "html.parser")
        # cards: links to *.devfolio.co subdomains
        cards = set()
        for a in soup.select("a[href*='.devfolio.co']"):
            parent = a.find_parent(["div", "section", "article"])
            cards.add(parent if parent else a)
        for c in cards:
            try:
                out.extend(parse_card(c))
            except Exception:
                continue
        # dedupe by link+track inside scraper
        seen, deduped = set(), []
        for h in out:
            k = (h.link, h.tech_stack)
            if k not in seen:
                seen.add(k)
                deduped.append(h)
        polite(delay)
        return deduped, None
    except Exception as e:
        return out, f"Devfolio: {e}"
