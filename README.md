
# AI Productivity Coach Bot — v4 (Render-ready)

Telegram bot for daily planning (MITs), Pomodoro focus, time tracking, reflections, weekly report, **streaks/badges**, **Google Calendar sync**, and **auto-timeboxing of MITs**.

## New in v4
- **render.yaml** for one-click Render (Background Worker + Persistent Disk)
- **init_repo.sh** push script template
- **Auto-schedule MITs to Google Calendar** after `/plan` if enabled

## Commands
- `/start`, `/help`
- `/plan` — capture 2–3 MITs (auto-schedules to Calendar if enabled)
- `/tasks`, `/done <task_id>`
- `/focus <work> <break>`
- `/starttask <name>`, `/stoptask`
- `/summary`, `/weekly`
- `/reflect`
- `/setreminders <morning> <evening>`
- `/calendar <task_id> <HH:MM> <duration_min>`
- `/export`, `/wipe`

## Env Vars
```
# Required
BOT_TOKEN=...
TZ=America/Los_Angeles

# DB
DB_PATH=/app/data/data.db        # For Render disk (or any path)

# Reminders (optional)
MORNING_REMINDER_HOUR=9
EVENING_REMINDER_HOUR=21

# Calendar (optional but required for autoschedule)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=
GOOGLE_CALENDAR_ID=primary

# Auto-Timebox (optional)
CALENDAR_AUTOSCHEDULE=1          # 1=on, 0=off
MIT_BLOCK_MIN=60                 # minutes per MIT
WORK_START=09:00                 # daily work window start (local TZ)
WORK_END=18:00                   # daily work window end (local TZ)
```
If autoscheduling is on but Google creds are missing, autoschedule is skipped gracefully.

## Deploy on Render
- As **Background Worker**: Build `pip install -r requirements.txt`, Start `python bot.py`
- Add a **Persistent Disk** at `/app/data` and set `DB_PATH=/app/data/data.db`
- Set env vars (above)
- Or use the provided `render.yaml` and deploy as a **Blueprint**

## Google refresh token
```
python oauth_refresh_token.py --client-id <ID> --client-secret <SECRET>
```
Copy the printed token into `GOOGLE_REFRESH_TOKEN`.
