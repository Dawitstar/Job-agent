"""Data types shared across the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EmailMessage:
    """A Gmail message reduced to what the parser needs."""

    id: str
    subject: str
    sender: str
    received_at: datetime | None
    text: str = ""
    html: str = ""


@dataclass
class JobPosting:
    """One job parsed out of a LinkedIn alert email."""

    job_id: str  # LinkedIn numeric job id; used as the dedupe key
    title: str
    company: str
    location: str
    link: str  # canonical https://www.linkedin.com/jobs/view/<id>/
    source_message_id: str = ""
    received_at: datetime | None = None
    extra: list[str] = field(default_factory=list)  # e.g. "Easy Apply", "Actively recruiting"
