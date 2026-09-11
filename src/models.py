"""Shared contract — Link is the primary key for lifelong upserts."""
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


class Hackathon(BaseModel):
    name: str = Field(min_length=1)
    platform: str  # Devpost | DoraHacks | Devfolio
    tech_stack: str  # AI | Blockchain (one row per track; dual-match -> two rows downstream)
    status: str  # Open | Upcoming | Closed (we only push Open/Upcoming, Closed kept on update)
    prize_pool: str = "Not specified"
    link: str
    # Days until submissions close. int -> Sheets stores a NUMBER (sorts
    # correctly); None -> blank cell (sinks to bottom on ascending sort).
    deadline_days: int | None = None

    @field_validator("link")
    @classmethod
    def normalize_link(cls, v: str) -> str:
        v = v.strip().split("?")[0].split("#")[0].rstrip("/")
        return v

    @field_validator("status")
    @classmethod
    def normalize_status(cls, v: str) -> str:
        s = v.strip().lower()
        if "open" in s or "live" in s or "left" in s or "accepting" in s:
            return "Open"
        if "upcoming" in s or "soon" in s or "starts in" in s or "pre-registration" in s:
            return "Upcoming"
        if "closed" in s or "ended" in s:
            return "Closed"
        return v.strip().title() or "Open"

    def row(self) -> list:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        days = self.deadline_days if self.deadline_days is not None else ""
        return [self.name, self.platform, self.tech_stack, self.status,
                self.prize_pool, days, self.link, today]
