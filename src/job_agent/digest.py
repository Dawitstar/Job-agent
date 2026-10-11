"""Ranked digest printed to the terminal."""

from __future__ import annotations

import textwrap

from .models import JobPosting
from .scorer import Score


def format_digest(results: list[tuple[JobPosting, Score]]) -> str:
    ranked = sorted(results, key=lambda r: r[1].score, reverse=True)
    out: list[str] = []
    for i, (job, s) in enumerate(ranked, 1):
        where = f" — {job.location}" if job.location else ""
        out.append(f"{i:2}. [{s.score:3}] {job.title} @ {job.company or '?'}{where}")
        out.append(f"          {job.link}")
        for reason in s.reasons:
            out.append(textwrap.fill(reason, width=100, initial_indent="          - ",
                                     subsequent_indent="            "))
        out.append("")
    return "\n".join(out)
