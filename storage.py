"""Results storage: Google Sheets (durable, external, primary) + a local
append-only CSV backup (redundant, never the sole store).

Streamlit Community Cloud's filesystem is ephemeral, so the Sheet is the
source of truth. The local CSV only helps if you're running locally or
want a quick offline copy; it is wiped on every cloud redeploy.

Interface is kept small and swappable: append_result(row) / completed(id).
A Postgres backend (Supabase/Neon via st.connection) would implement the
same two functions and could be swapped in without touching app.py.
"""

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


def completed(curator_id: str) -> set[tuple[str, int]]:
    """(image_id, repeat_index) pairs this curator has already rated.

    Used to filter the queue on load/resume, and as a belt-and-suspenders
    guard against double-writes on refresh/re-submit.
    """
    ws = _worksheet()
    records = ws.get_all_records()  # list[dict] keyed by header row
    done = set()
    for r in records:
        if str(r.get("curator_id")) == str(curator_id):
            image_id = r.get("image_id")
            try:
                repeat_index = int(r.get("repeat_index", 0))
            except (TypeError, ValueError):
                repeat_index = 0
            done.add((image_id, repeat_index))
    return done
