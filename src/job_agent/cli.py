"""Command-line entry point: ``job-agent <command>``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_settings
from .models import JobPosting
from .parser import is_linkedin_job_alert, load_eml, parse_email


def _print_jobs(jobs: list[JobPosting]) -> None:
    for i, job in enumerate(jobs, 1):
        where = f" — {job.location}" if job.location else ""
        print(f"{i:3}. {job.title} @ {job.company or '?'}{where}")
        print(f"     {job.link}")
    print(f"\n{len(jobs)} job(s)")


def _jobs_from_gmail(query: str | None, max_results: int) -> list[JobPosting]:
    from .gmail_client import build_service, fetch_messages

    settings = load_settings()
    service = build_service(settings.credentials_file, settings.token_file)
    query = query or settings.gmail_query

    jobs: dict[str, JobPosting] = {}
    n_messages = 0
    for msg in fetch_messages(service, query, max_results=max_results):
        if not is_linkedin_job_alert(msg):
            continue
        n_messages += 1
        for job in parse_email(msg):
            jobs.setdefault(job.job_id, job)

    print(f"Parsed {n_messages} alert email(s) for query: {query}\n", file=sys.stderr)
    return list(jobs.values())


def _jobs_from_eml(paths: list[str]) -> list[JobPosting]:
    jobs: dict[str, JobPosting] = {}
    for path in paths:
        for job in parse_email(load_eml(Path(path))):
            jobs.setdefault(job.job_id, job)
    return list(jobs.values())


def cmd_fetch(args: argparse.Namespace) -> int:
    _print_jobs(_jobs_from_gmail(args.query, args.max))
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    _print_jobs(_jobs_from_eml(args.files))
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    import anthropic

    from .digest import format_digest
    from .scorer import Scorer, ScoringError

    settings = load_settings()
    for f in (settings.profile_file, settings.cv_file):
        if not f.exists():
            print(f"Missing {f}. Copy {f.stem}.example.md to {f.name} and fill it in.", file=sys.stderr)
            return 1

    jobs = _jobs_from_eml(args.eml) if args.eml else _jobs_from_gmail(args.query, args.max)
    if not jobs:
        print("No jobs found.", file=sys.stderr)
        return 0

    scorer = Scorer(settings.profile_file.read_text(), settings.cv_file.read_text(), settings.model)
    results = []
    for i, job in enumerate(jobs, 1):
        print(f"Scoring {i}/{len(jobs)}: {job.title} @ {job.company}", file=sys.stderr)
        try:
            results.append((job, scorer.score(job)))
        except (ScoringError, anthropic.APIConnectionError, anthropic.RateLimitError,
                anthropic.InternalServerError) as e:
            # Skip this job; bad credentials or a bad request still stop the run.
            print(f"  skipped: {e}", file=sys.stderr)

    print()
    print(format_digest(results))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="job-agent", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="Read LinkedIn alert emails from Gmail and list the jobs")
    f.add_argument("--query", help="Gmail search query (default from JOB_AGENT_GMAIL_QUERY)")
    f.add_argument("--max", type=int, default=50, help="Max emails to read (default 50)")
    f.set_defaults(func=cmd_fetch)

    s = sub.add_parser("score", help="Score jobs against profile.md and cv.md and print a ranked digest")
    s.add_argument("--eml", nargs="+", help="Score jobs from saved .eml files instead of Gmail")
    s.add_argument("--query", help="Gmail search query (default from JOB_AGENT_GMAIL_QUERY)")
    s.add_argument("--max", type=int, default=50, help="Max emails to read (default 50)")
    s.set_defaults(func=cmd_score)

    e = sub.add_parser("parse", help="Parse saved .eml files offline (no Gmail access)")
    e.add_argument("files", nargs="+")
    e.set_defaults(func=cmd_parse)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
