import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.filter import classify, is_eligible
from src.models import Hackathon


def test_ai():
    assert classify("Machine Learning/AI", "Nebius x NVIDIA Global AI Hackathon") == {"AI"}


def test_blockchain():
    assert "Blockchain" in classify("Crypto / PQC", "Build with CMC API Hackathon")


def test_dual():
    assert classify("AI Blockchain", "AI x Web3 Hack") == {"AI", "Blockchain"}


def test_eligible():
    assert is_eligible("Open") and is_eligible("Upcoming") and not is_eligible("Closed")


def test_model_row():
    h = Hackathon(name="X", platform="Devpost", tech_stack="AI", status="Open", prize_pool="$10", link="https://x.devpost.com/?utm=a")
    assert h.link == "https://x.devpost.com"
    assert len(h.row()) == 8
    assert h.row()[5] == ""  # no deadline -> blank


def test_model_days_numeric():
    h = Hackathon(name="X", platform="DoraHacks", tech_stack="AI", status="Open",
                  prize_pool="5000 USD", link="https://dorahacks.io/hackathon/x", deadline_days=12)
    assert h.row()[5] == 12 and isinstance(h.row()[5], int)


def test_devpost_days_left():
    from src.scrapers.devpost import _days_left
    assert _days_left({"time_left_to_submission": "20 days left"}) == 20
    assert _days_left({"time_left_to_submission": "4 days left"}) == 4
    assert _days_left({"time_left_to_submission": "about 1 month left"}) == 30
    assert _days_left({"time_left_to_submission": "about 2 months left"}) == 60
    assert _days_left({}) is None


def test_dorahacks_days():
    import time
    from src.scrapers.dorahacks import parse_api_item
    now = int(time.time())
    rows = parse_api_item({"title": "AI Sprint", "uname": "ai-sprint",
                           "tags": "AI", "ecosystem": "",
                           "timeline_pre_register": 0,
                           "timeline_start": now - 86400,
                           "timeline_end": now + 10 * 86400,
                           "bonus_price": 1000, "bonus_token": "USD"}, now)
    assert rows and rows[0].status == "Open" and rows[0].deadline_days == 10
