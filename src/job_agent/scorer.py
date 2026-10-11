"""Fit scoring with the Anthropic API. Not implemented yet.

Plan: send profile.md, cv.md and one JobPosting to the configured model
(default ``claude-sonnet-5-5``) and get back JSON ``{"score": 0-100, "reasons": [...]}``.
"""

from __future__ import annotations

from .models import JobPosting


def score_job(job: JobPosting, profile: str, cv: str, model: str) -> dict:
    raise NotImplementedError("Scoring is the next milestone.")
