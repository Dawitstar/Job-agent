import base64
from pathlib import Path

from job_agent.gmail_client import message_from_gmail_payload
from job_agent.models import EmailMessage
from job_agent.parser import parse_email, parse_html, parse_text

FIXTURES = Path(__file__).parent / "fixtures"


def _fields(jobs):
    return [(j.job_id, j.title, j.company, j.location, j.link) for j in jobs]


def test_parse_text_alert():
    jobs = parse_text((FIXTURES / "alert.txt").read_text())
    assert _fields(jobs) == [
        ("3812345678", "Senior Software Engineer", "Acme Corp", "Seattle, WA (Hybrid)",
         "https://www.linkedin.com/jobs/view/3812345678/"),
        ("3899990001", "Backend Engineer, Payments", "Globex", "Remote",
         "https://www.linkedin.com/jobs/view/3899990001/"),
        ("3899990002", "Alumni Relations Engineer", "Initech", "Bellevue, WA",
         "https://www.linkedin.com/jobs/view/3899990002/"),
    ]
    assert jobs[0].extra == ["Actively recruiting", "3 connections"]
    assert "$150K/yr - $190K/yr" in jobs[2].extra


def test_parse_html_alert():
    jobs = parse_html((FIXTURES / "alert.html").read_text())
    assert _fields(jobs) == [
        ("3812345678", "Senior Software Engineer", "Acme Corp", "Seattle, WA (Hybrid)",
         "https://www.linkedin.com/jobs/view/3812345678/"),
        ("3899990001", "Backend Engineer, Payments", "Globex", "Remote",
         "https://www.linkedin.com/jobs/view/3899990001/"),
    ]


def test_parse_email_falls_back_to_html():
    msg = EmailMessage(id="m1", subject="", sender="jobalerts-noreply@linkedin.com",
                       received_at=None, text="", html=(FIXTURES / "alert.html").read_text())
    jobs = parse_email(msg)
    assert len(jobs) == 2
    assert all(j.source_message_id == "m1" for j in jobs)


def test_gmail_payload_decoding():
    def b64(s):
        return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")

    raw = {
        "id": "abc",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "Subject", "value": "Software engineer: Acme Corp and more"},
                {"name": "From", "value": "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>"},
                {"name": "Date", "value": "Sat, 10 Oct 2026 08:00:00 +0000"},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": b64((FIXTURES / "alert.txt").read_text())}},
                {"mimeType": "text/html", "body": {"data": b64("<p>hi</p>")}},
            ],
        },
    }
    msg = message_from_gmail_payload(raw)
    assert msg.subject.startswith("Software engineer")
    assert msg.received_at.year == 2026
    assert msg.html == "<p>hi</p>"
    assert len(parse_email(msg)) == 3


def test_load_eml():
    from job_agent.parser import load_eml

    msg = load_eml(FIXTURES / "sample-alert.eml")
    assert msg.sender.endswith("<jobalerts-noreply@linkedin.com>")
    assert [j.job_id for j in parse_email(msg)] == ["3812345678", "3899990001", "3899990002"]


def test_forwarded_alert_with_card_wrapping_link():
    # Yahoo forward: text part has no links, sender is not LinkedIn, and each
    # card is wrapped in one big link around the title link.
    from job_agent.parser import is_linkedin_job_alert

    msg = EmailMessage(id="fw", subject="Fw: Operations Manager at Contoso Foods",
                       sender="someone@yahoo.com", received_at=None,
                       text="Begin forwarded message:\n| Operations Manager |\n Contoso Foods · Toronto, ON\n",
                       html=(FIXTURES / "forwarded_alert.html").read_text())
    assert is_linkedin_job_alert(msg)
    jobs = parse_email(msg)
    assert [(j.job_id, j.title, j.company, j.location) for j in jobs] == [
        ("4000000001", "Operations Manager", "Contoso Foods", "Toronto, ON (On-site)"),
        ("4000000002", "Site Director", "Fabrikam", "Mississauga, ON"),
    ]
    assert jobs[0].extra == ["CA$80K-CA$90K / year", "Actively recruiting", "Easy Apply"]
    assert jobs[1].extra == ["13 connections", "Fast growing"]


def test_non_alert_is_rejected():
    from job_agent.parser import is_linkedin_job_alert

    msg = EmailMessage(id="x", subject="hi", sender="friend@yahoo.com", received_at=None,
                       text="lunch?", html="")
    assert not is_linkedin_job_alert(msg)
