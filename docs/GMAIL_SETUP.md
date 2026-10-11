# Gmail setup

One-time setup so `job-agent fetch` can read your LinkedIn job alerts. It takes about 10 minutes and is free.

job-agent only asks for **read-only** access (`gmail.readonly`). It can't send, delete, or change email.

Do this on **your own computer**. The sign-in step opens a browser on that machine.

---

## 1. Create a Google Cloud project

1. Go to <https://console.cloud.google.com/> and sign in with the Google account whose Gmail gets the LinkedIn alerts. If this is your first visit, accept the terms.
2. Click the **project picker** in the top bar, then **New project**.
3. Name it `job-agent` and click **Create**.
4. Make sure the new project is selected in the project picker.

## 2. Turn on the Gmail API

1. Open <https://console.cloud.google.com/apis/library/gmail.googleapis.com>.
2. Check that `job-agent` is the selected project, then click **Enable**.

## 3. Set up the consent screen

In the menu, go to **APIs & Services → OAuth consent screen**. Newer consoles call this **Google Auth Platform**.

1. Click **Get started**.
2. **App information:** App name `job-agent`. User support email: your address.
3. **Audience:** choose **External**.
4. **Contact information:** your address.
5. Agree to the policy and click **Create**.
6. Open **Audience**, find **Test users**, click **Add users**, enter **your Gmail address**, and save.
   Skipping this step causes `Error 403: access_denied` later.

You don't need to publish or verify the app. It stays in **Testing** mode, which is fine for personal use.

## 4. Create the OAuth client

1. Go to **Clients**, or **APIs & Services → Credentials** in older consoles. Click **Create client** (or **Create credentials → OAuth client ID**).
2. **Application type:** choose **Desktop app**. Name: `job-agent desktop`.
3. Click **Create**, then **Download JSON**.
4. Rename the downloaded file to **`credentials.json`** and move it into the project folder, next to `pyproject.toml`:

```
Job-agent/
├── credentials.json   ← here
├── pyproject.toml
└── src/
```

Keep this file private. It is already in `.gitignore`.

## 5. First run

From the project folder, with the virtualenv active:

```bash
job-agent fetch --max 5
```

1. A browser tab opens. Pick your Gmail account.
2. Google warns **"Google hasn't verified this app"**. That's expected, because this is your own app. Click **Continue**.
3. Allow **"View your email messages and settings"**, which is the read-only permission.
4. The tab shows *"The authentication flow has completed."* Go back to the terminal.

The login is saved to `token.json` (git-ignored), so later runs don't open the browser.

Try a wider search:

```bash
job-agent fetch                                        # last 7 days (default)
job-agent fetch --query 'from:jobalerts-noreply@linkedin.com newer_than:30d' --max 100
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Error 403: access_denied` in the browser | Add your Gmail address as a **test user** (step 3.6). |
| `OAuth client file not found` | `credentials.json` isn't in the folder you ran the command from. Move it there, or set `JOB_AGENT_CREDENTIALS=/path/to/credentials.json`. |
| `Gmail API has not been used in project … or it is disabled` | Do step 2 for the same project, then wait a minute. |
| Browser opens again after about a week | Expected in Testing mode: Google expires the saved login after 7 days. Sign in again; the old token is replaced automatically. |
| `0 job(s)` | Paste the query into the Gmail search box. If nothing matches, your alerts come from a different sender. Open one, copy the sender address, and use it with `--query 'from:<sender> newer_than:30d'`. |
| Running on a server with no browser | Do the first run on a computer with a browser, then copy `token.json` to the server. |

## Revoking access

Open <https://myaccount.google.com/permissions>, choose **job-agent**, and remove access. Then delete `token.json`.
