"""Results storage: Google Sheets (durable, external, primary) + a local
append-only CSV backup (redundant, never the sole store).

Streamlit Community Cloud's filesystem is ephemeral, so the Sheet is the
source of truth. The local CSV only helps if you're running locally or
want a quick offline copy; it is wiped on every cloud redeploy.

Interface is kept small and swappable: append_result(row) /
resume_or_new_session(id, total). A Postgres backend (Supabase/Neon via
st.connection) would implement the same two functions and could be
swapped in without touching app.py.

Sessions: a curator_id is free text (no fixed roster) and can attempt the
survey more than once over time. Each attempt is a "session", its own
session_id, its own deterministic image order (assignment.build_queue is
seeded by session_id, not curator_id). A session is "complete" once it has
as many rows as the queue is long. resume_or_new_session() finds a
curator_id's most recent session and either resumes it (if incomplete) or
mints a fresh one (if complete or nonexistent).
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
import csv

import streamlit as st

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:  # allows scripts/analyze.py-free local smoke tests
    gspread = None
    Credentials = None

COLUMNS = [
    "timestamp_iso",
    "curator_id",
    "session_id",
    "image_id",
    "repeat_index",
    "score",
    "unsure",
    "dwell_seconds",
    "slider_touched",
    "queue_position",
    "app_version",
]

LOCAL_BACKUP_PATH = Path("results_backup.csv")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource(show_spinner=False)
def _worksheet():
    """Open (and fail loudly on) the results worksheet.

    Cached per-process: one gspread client/session for the app's lifetime.
    """
    if gspread is None:
        raise RuntimeError(
            "gspread/google-auth not installed. Add them to requirements.txt."
        )
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        sheet_key = st.secrets["sheet_key"]
    except KeyError as e:
        raise RuntimeError(
            f"Missing Streamlit secret {e}. See .streamlit/secrets.toml.example."
        ) from e

    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)

    try:
        sheet = client.open_by_key(sheet_key)
        ws = sheet.sheet1
    except Exception as e:  # noqa: BLE001 - fail loudly per spec
        raise RuntimeError(
            f"Could not reach Google Sheet (key={sheet_key!r}). "
            f"Check sharing + secrets. Original error: {e}"
        ) from e

    # Ensure header row exists (first run against a fresh sheet).
    first_row = ws.row_values(1)
    if first_row != COLUMNS:
        if first_row:
            raise RuntimeError(
                "Results sheet header row doesn't match expected COLUMNS. "
                f"Found: {first_row}. Fix the sheet or COLUMNS."
            )
        ws.append_row(COLUMNS, value_input_option="RAW")

    return ws


def _row_to_values(row: dict) -> list:
    return [row.get(col, "") for col in COLUMNS]


def append_result(row: dict) -> None:
    """Append one rating row immediately. Called once per image advance.

    `row` must contain (a subset of) COLUMNS keys; missing keys are
    written blank. timestamp_iso and app_version are filled in if absent.
    """
    row = dict(row)
    row.setdefault("timestamp_iso", datetime.now(timezone.utc).isoformat())
    row.setdefault("app_version", "1.0")

    ws = _worksheet()
    ws.append_row(_row_to_values(row), value_input_option="RAW")

    _append_local_backup(row)


def _append_local_backup(row: dict) -> None:
    """Best-effort redundant local CSV append. Never the sole store."""
    try:
        is_new = not LOCAL_BACKUP_PATH.exists()
        with open(LOCAL_BACKUP_PATH, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            if is_new:
                writer.writeheader()
            writer.writerow({col: row.get(col, "") for col in COLUMNS})
    except OSError:
        pass  # local backup is a convenience only; never block on it


def _new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def resume_or_new_session(curator_id: str, total_items: int) -> tuple[str, set[tuple[str, int]]]:
    """Decide which session this curator_id should continue (or start).

    Returns (session_id, done) where `done` is the set of (image_id,
    repeat_index) pairs already recorded in that session, empty for a
    brand-new session.

    Logic: look at this curator_id's most recent session (by latest
    timestamp among its rows). If it has fewer rows than `total_items`,
    it's unfinished, resume it. Otherwise (finished, or no session
    exists yet), start a new one. This is also the double-write guard:
    resuming replays the same session_id/queue, so items already in
    `done` are skipped rather than re-appended.
    """
    ws = _worksheet()
    records = ws.get_all_records()  # list[dict] keyed by header row
    rows = [r for r in records if str(r.get("curator_id")) == str(curator_id)]

    if not rows:
        return _new_session_id(), set()

    sessions: dict[str, list[dict]] = {}
    for r in rows:
        sessions.setdefault(str(r.get("session_id")), []).append(r)

    latest_sid = max(
        sessions, key=lambda sid: max(r.get("timestamp_iso", "") for r in sessions[sid])
    )
    latest_rows = sessions[latest_sid]

    if len(latest_rows) >= total_items:
        return _new_session_id(), set()  # last session finished -> fresh attempt

    done = set()
    for r in latest_rows:
        image_id = r.get("image_id")
        try:
            repeat_index = int(r.get("repeat_index", 0))
        except (TypeError, ValueError):
            repeat_index = 0
        done.add((image_id, repeat_index))
    return latest_sid, done
