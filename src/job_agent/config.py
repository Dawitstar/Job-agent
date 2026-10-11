"""Paths and settings. Everything can be overridden with environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _path(env: str, default: Path) -> Path:
    return Path(os.environ.get(env, default)).expanduser()


@dataclass(frozen=True)
class Settings:
    root: Path
    credentials_file: Path  # OAuth client secret downloaded from Google Cloud Console
    token_file: Path  # cached user token, created on first login
    db_file: Path
    profile_file: Path
    cv_file: Path
    gmail_query: str
    model: str


def load_settings() -> Settings:
    root = _path("JOB_AGENT_HOME", Path.cwd())
    return Settings(
        root=root,
        credentials_file=_path("JOB_AGENT_CREDENTIALS", root / "credentials.json"),
        token_file=_path("JOB_AGENT_TOKEN", root / "token.json"),
        db_file=_path("JOB_AGENT_DB", root / "data" / "jobs.db"),
        profile_file=_path("JOB_AGENT_PROFILE", root / "profile.md"),
        cv_file=_path("JOB_AGENT_CV", root / "cv.md"),
        gmail_query=os.environ.get(
            "JOB_AGENT_GMAIL_QUERY",
            # The quoted address also matches alerts forwarded from another inbox.
            '(from:jobalerts-noreply@linkedin.com OR "jobalerts-noreply@linkedin.com") newer_than:7d',
        ),
        model=os.environ.get("JOB_AGENT_MODEL", "claude-sonnet-5-5"),
    )
