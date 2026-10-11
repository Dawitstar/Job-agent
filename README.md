# job-agent

Reads LinkedIn job-alert emails from your Gmail, pulls out each job, scores how well it fits your profile and CV with Claude, saves the results to SQLite and prints a ranked digest.

- Gmail access is **read-only** (`gmail.readonly` scope).
- **No scraping:** it only reads the alert emails LinkedIn already sent you. Job links are rebuilt from the job ID in the email, and nothing is fetched from linkedin.com.
- **No auto-applying.**

## Status

| Stage | Module | Status |
|---|---|---|
| Gmail OAuth + fetch | `gmail_client.py` | done |
| Alert email parser | `parser.py` | done |
| Fit scoring (Anthropic API) | `scorer.py` | stub |
| SQLite storage | `db.py` | stub |
| Ranked digest | `digest.py` | stub |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp profile.example.md profile.md   # edit
cp cv.example.md cv.md             # edit
```

### Gmail OAuth

1. In the [Google Cloud Console](https://console.cloud.google.com/), create a project and enable the **Gmail API**.
2. Set up the OAuth consent screen (External, add yourself as a test user).
3. Create credentials of type **OAuth client ID → Desktop app**, download the JSON and save it as `credentials.json` in the project root.
4. Run `job-agent fetch`. A browser window opens for consent the first time. The token is cached in `token.json`.

`credentials.json`, `token.json`, `profile.md`, `cv.md` and `data/` are git-ignored.

## Usage

```bash
job-agent fetch                                   # last 7 days of alerts
job-agent fetch --query 'from:jobalerts-noreply@linkedin.com newer_than:1d' --max 10
job-agent parse saved-alert.eml                   # offline, no Gmail needed
```

## Configuration (environment variables)

| Variable | Default |
|---|---|
| `JOB_AGENT_HOME` | current directory |
| `JOB_AGENT_CREDENTIALS` | `$JOB_AGENT_HOME/credentials.json` |
| `JOB_AGENT_TOKEN` | `$JOB_AGENT_HOME/token.json` |
| `JOB_AGENT_DB` | `$JOB_AGENT_HOME/data/jobs.db` |
| `JOB_AGENT_PROFILE` / `JOB_AGENT_CV` | `profile.md` / `cv.md` |
| `JOB_AGENT_GMAIL_QUERY` | `from:jobalerts-noreply@linkedin.com newer_than:7d` |
| `JOB_AGENT_MODEL` | `claude-sonnet-5-5` |

## How parsing works

The parser prefers the email's plain-text part. There, each job is a block of lines ending in `View job: https://www.linkedin.com/comm/jobs/view/<id>/...`. The last three content lines in the block are title, company and location, and badge lines such as "Actively recruiting" or "3 connections" are stored in `extra`. If there is no usable text part, it falls back to the HTML part and groups links by job ID. Jobs are de-duplicated by LinkedIn job ID.

LinkedIn changes its email templates from time to time. If parsing looks wrong, save the email as `.eml` and run it through `job-agent parse`, then add it under `tests/fixtures/`.

## Tests

```bash
pytest
```
