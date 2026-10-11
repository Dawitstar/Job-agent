"""Read-only Gmail access via OAuth (installed-app flow).

Only the ``gmail.readonly`` scope is requested: this code can list and read
messages, nothing else.
"""

from __future__ import annotations

import base64
import email.utils
from collections.abc import Iterator
from pathlib import Path

from .models import EmailMessage

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_credentials(credentials_file: Path, token_file: Path):
    """Load cached credentials, refreshing or running the browser login as needed."""
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            # Apps in "Testing" mode get refresh tokens that expire after 7 days.
            creds = None

    if not (creds and creds.valid):
        if not credentials_file.exists():
            raise FileNotFoundError(
                f"OAuth client file not found: {credentials_file}. "
                "Create a Desktop OAuth client in Google Cloud Console and save it there."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
        creds = flow.run_local_server(port=0)

    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json())
    token_file.chmod(0o600)
    return creds


def build_service(credentials_file: Path, token_file: Path):
    from googleapiclient.discovery import build

    creds = get_credentials(credentials_file, token_file)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def list_message_ids(service, query: str, max_results: int | None = None) -> Iterator[str]:
    """Yield message ids matching a Gmail search query, following pagination."""
    page_token = None
    seen = 0
    while True:
        resp = (
            service.users()
            .messages()
            .list(userId="me", q=query, pageToken=page_token, maxResults=100)
            .execute()
        )
        for m in resp.get("messages", []):
            yield m["id"]
            seen += 1
            if max_results is not None and seen >= max_results:
                return
        page_token = resp.get("nextPageToken")
        if not page_token:
            return


def get_message(service, message_id: str) -> EmailMessage:
    raw = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    return message_from_gmail_payload(raw)


def fetch_messages(
    service, query: str, max_results: int | None = None
) -> Iterator[EmailMessage]:
    for mid in list_message_ids(service, query, max_results):
        yield get_message(service, mid)


# --- payload decoding (pure functions, testable without the API) -------------


def message_from_gmail_payload(raw: dict) -> EmailMessage:
    payload = raw.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

    received_at = None
    if "date" in headers:
        try:
            received_at = email.utils.parsedate_to_datetime(headers["date"])
        except (TypeError, ValueError):
            pass

    texts: list[str] = []
    htmls: list[str] = []
    _collect_bodies(payload, texts, htmls)

    return EmailMessage(
        id=raw.get("id", ""),
        subject=headers.get("subject", ""),
        sender=headers.get("from", ""),
        received_at=received_at,
        text="\n".join(texts),
        html="\n".join(htmls),
    )


def _collect_bodies(part: dict, texts: list[str], htmls: list[str]) -> None:
    mime = part.get("mimeType", "")
    data = part.get("body", {}).get("data")
    if data and mime == "text/plain":
        texts.append(_b64url_decode(data))
    elif data and mime == "text/html":
        htmls.append(_b64url_decode(data))
    for sub in part.get("parts", []) or []:
        _collect_bodies(sub, texts, htmls)


def _b64url_decode(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
