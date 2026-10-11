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


def cmd_fetch(args: argparse.Namespace) -> int:
    from .gmail_client import build_service, fetch_messages

    settings = load_settings()
    service = build_service(settings.credentials_file, settings.token_file)
    query = args.query or settings.gmail_query

    jobs: dict[str, JobPosting] = {}
    n_messages = 0
    for msg in fetch_messages(service, query, max_results=args.max):
        if not is_linkedin_job_alert(msg):
            continue
        n_messages += 1
        for job in parse_email(msg):
            jobs.setdefault(job.job_id, job)

    print(f"Parsed {n_messages} alert email(s) for query: {query}\n")
    _print_jobs(list(jobs.values()))
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    jobs: dict[str, JobPosting] = {}
    for path in args.files:
        for job in parse_email(load_eml(Path(path))):
            jobs.setdefault(job.job_id, job)
    _print_jobs(list(jobs.values()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="job-agent", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="Read LinkedIn alert emails from Gmail and list the jobs")
    f.add_argument("--query", help="Gmail search query (default from JOB_AGENT_GMAIL_QUERY)")
    f.add_argument("--max", type=int, default=50, help="Max emails to read (default 50)")
    f.set_defaults(func=cmd_fetch)

    e = sub.add_parser("parse", help="Parse saved .eml files offline (no Gmail access)")
    e.add_argument("files", nargs="+")
    e.set_defaults(func=cmd_parse)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
