"""Keyword + tag matcher. Pure function — easy to test, never breaks runs."""
import re

AI_KEYWORDS = ["ai", "artificial intelligence", "machine learning", "llm", "genai", "ai/ml", "ai agents", "deep learning", "ml"]
BLOCKCHAIN_KEYWORDS = ["blockchain", "web3", "crypto", "ethereum", "smart contract", "smart contracts", "defi", "solidity", "pqc", "token"]


def _haystack(*parts: str) -> str:
    return " | ".join(p or "" for p in parts).lower()


def classify(text_tags: str, title: str = "", description: str = "") -> set:
    """Return {'AI'} / {'Blockchain'} / both / empty."""
    hay = _haystack(text_tags, title, description)
    out = set()
    for kw in AI_KEYWORDS:
        # short tokens need word boundaries ("ai" should not match "fair")
        pat = r"\bai\b" if kw in ("ai", "ml") else re.escape(kw)
        if re.search(pat, hay):
            out.add("AI")
            break
    for kw in BLOCKCHAIN_KEYWORDS:
        if kw in hay:
            out.add("Blockchain")
            break
    return out


def is_eligible(status: str) -> bool:
    return status.strip().lower() in ("open", "upcoming")
