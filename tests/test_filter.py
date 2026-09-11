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
    assert len(h.row()) == 7
