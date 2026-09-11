"""Shared HTTP helpers: UA, retries, polite delay."""
import time
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HackathonScout/1.0 (+github-actions)",
    "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def get(session_: requests.Session, url: str, timeout: int = 20, **kwargs) -> requests.Response:
    r = session_.get(url, timeout=timeout, **kwargs)
    r.raise_for_status()
    return r


def polite(delay: float = 1.0):
    time.sleep(delay)
