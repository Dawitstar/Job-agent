"""Parse LinkedIn job-alert emails into JobPosting records.

Works only on the email body Gmail already delivered; nothing here fetches
anything from linkedin.com. The plain-text part is preferred because its
layout is simple and stable; the HTML part is a fallback.

Plain-text alerts look roughly like::

    Senior Software Engineer
    Acme Corp
    Seattle, WA (Hybrid)
    Actively recruiting
    View job: https://www.linkedin.com/comm/jobs/view/3812345678/?trackingId=...

    ---------------------------------------------------------
"""

from __future__ import annotations

import email
import email.policy
import email.utils
import re
from pathlib import Path

from .models import EmailMessage, JobPosting

JOB_URL_RE = re.compile(r"https?://[\w.]*linkedin\.com/(?:comm/)?jobs/view/(\d+)[^\s<>\"')]*")
SEPARATOR_RE = re.compile(r"^\s*[-_=]{5,}\s*$")

# Lines that are badges/metadata, not title/company/location.
NOISE_RE = re.compile(
    r"(^actively (recruiting|hiring)|actively hiring$|^easy apply$|^promoted$|"
    r"\b\d[\d,]*\+?\s+applicants?\b|early applicant|"
    r"\b\d+\s+(connections?|(school )?alumni)\b|\bworks? here\b|"
    r"^apply with (your )?(resume|profile)|^be among the first|"
    r"\b\d+\s+(minutes?|hours?|days?|weeks?)\s+ago\b|"
    r"top applicant|in your network|response insights|^reposted|^fast growing$|"
    r"^[A-Z]{0,3}[$€£][\d,.]+[kK]?\b|/\s*(yr|year|hr|hour|month)\b)",
    re.IGNORECASE,
)

# Email chrome that can end up in the same block as the first job.
HEADER_RE = re.compile(
    r"(^your job alert|new jobs? match|jobs? you may be interested|"
    r"^view all jobs|^see all jobs|^linkedin$|^unsubscribe|^manage (your )?alerts?|"
    r"^this email was intended|^you are receiving|^learn why we included this|"
    r"^©|^help:|^\d+\+? new jobs?)",
    re.IGNORECASE,
)

MIDDOT_SPLIT_RE = re.compile(r"\s+[·•|]\s+")


def canonical_job_url(job_id: str) -> str:
    return f"https://www.linkedin.com/jobs/view/{job_id}/"


ALERT_SENDER = "jobalerts-noreply@linkedin.com"


def is_linkedin_job_alert(msg: EmailMessage) -> bool:
    """True for alerts sent by LinkedIn, and for alerts forwarded from another inbox."""
    if "linkedin.com" in msg.sender.lower():
        return True
    return ALERT_SENDER in msg.text or ALERT_SENDER in msg.html


def parse_email(msg: EmailMessage) -> list[JobPosting]:
    """Parse one alert email. Uses the text part, falling back to HTML."""
    jobs = parse_text(msg.text) if msg.text else []
    if not jobs and msg.html:
        jobs = parse_html(msg.html)
    for job in jobs:
        job.source_message_id = msg.id
        job.received_at = msg.received_at
    return jobs


# --- plain text ---------------------------------------------------------------


def parse_text(text: str) -> list[JobPosting]:
    jobs: dict[str, JobPosting] = {}
    buffer: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if SEPARATOR_RE.match(line):
            buffer = []
            continue

        match = JOB_URL_RE.search(line)
        if match:
            job_id = match.group(1)
            # Text before the URL on the same line ("View job:") is just a label.
            if job_id not in jobs:
                job = _job_from_lines(job_id, buffer)
                if job:
                    jobs[job_id] = job
            buffer = []
            continue

        buffer.append(line)

    return list(jobs.values())


def _job_from_lines(job_id: str, lines: list[str]) -> JobPosting | None:
    core: list[str] = []
    extra: list[str] = []
    for line in lines:
        if HEADER_RE.search(line):
            continue
        (extra if NOISE_RE.search(line) else core).append(line)

    # Header leftovers can precede the card, so the card is the *last* lines.
    if not core:
        return None
    if len(core) == 1:
        title, company, location = core[0], "", ""
    elif len(core) == 2:
        title, rest = core
        company, location = _split_company_location(rest)
    else:
        title, company, location = core[-3:]

    return JobPosting(
        job_id=job_id,
        title=title,
        company=company,
        location=location,
        link=canonical_job_url(job_id),
        extra=extra,
    )


def _split_company_location(line: str) -> tuple[str, str]:
    parts = MIDDOT_SPLIT_RE.split(line, maxsplit=1)
    return (parts[0], parts[1]) if len(parts) == 2 else (line, "")


# --- HTML fallback ------------------------------------------------------------


def parse_html(html: str) -> list[JobPosting]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    anchors_by_id: dict[str, list] = {}
    for a in soup.find_all("a", href=True):
        m = JOB_URL_RE.search(a["href"])
        if m:
            anchors_by_id.setdefault(m.group(1), []).append(a)

    jobs: list[JobPosting] = []
    for job_id, anchors in anchors_by_id.items():
        card = _card_container(anchors[0], job_id)
        title = _anchor_title(anchors)
        strings = [s for s in card.stripped_strings if not HEADER_RE.search(s)]

        # Company/location are the non-noise strings that follow the title.
        after = strings[strings.index(title) + 1:] if title in strings else strings
        core = [s for s in after if not NOISE_RE.search(s) and s != title]
        extra = [s for s in after if NOISE_RE.search(s)]

        if not title and core:
            title = core.pop(0)
        if not title:
            continue

        company, location = "", ""
        if core:
            company, location = _split_company_location(core[0])
            if not location and len(core) > 1:
                location = core[1]

        jobs.append(
            JobPosting(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                link=canonical_job_url(job_id),
                extra=extra,
            )
        )
    return jobs


def _card_container(anchor, job_id: str):
    """Largest ancestor of ``anchor`` whose job links all point to ``job_id``."""
    node = anchor
    while node.parent is not None and node.parent.name not in (None, "[document]", "body", "html"):
        ids = {
            m.group(1)
            for a in node.parent.find_all("a", href=True)
            if (m := JOB_URL_RE.search(a["href"]))
        }
        if ids - {job_id}:
            break
        node = node.parent
    return node


def _anchor_title(anchors) -> str:
    # Some templates wrap the whole card in one link, so use the first string
    # inside a link, not the link's full text.
    for a in anchors:
        for text in a.stripped_strings:
            if not NOISE_RE.search(text) and not text.lower().startswith("view"):
                return text
    return ""


# --- offline helper -----------------------------------------------------------


def load_eml(path: Path) -> EmailMessage:
    """Load a saved .eml file (e.g. Gmail "Download message") for offline parsing."""
    msg = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
    text_part = msg.get_body(preferencelist=("plain",))
    html_part = msg.get_body(preferencelist=("html",))
    received_at = None
    if msg["Date"]:
        try:
            received_at = email.utils.parsedate_to_datetime(str(msg["Date"]))
        except (TypeError, ValueError):
            pass
    return EmailMessage(
        id=path.stem,
        subject=str(msg["Subject"] or ""),
        sender=str(msg["From"] or ""),
        received_at=received_at,
        text=text_part.get_content() if text_part else "",
        html=html_part.get_content() if html_part else "",
    )
