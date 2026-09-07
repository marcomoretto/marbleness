"""Results storage: Google Sheets (durable, external, primary) + a local
append-only CSV backup (redundant, never the sole store).

Streamlit Community Cloud's filesystem is ephemeral, so the Sheet is the
source of truth. The local CSV only helps if you're running locally or
want a quick offline copy; it is wiped on every cloud redeploy.

Interface is kept small and swappable: append_result(row), id_status(id),
assign_new_id(candidate_fn). A Postgres backend (Supabase/Neon via
st.connection) would implement the same functions and could be swapped in
without touching app.py.

Identity model: curator_id is a one-time, system-assigned identifier (see
assign_new_id), never freely chosen. It maps 1:1 to exactly one lifetime
attempt at the survey: id_status() reports whether it's never been used,
in progress (fewer rows than the queue is long, resumable), or completed
(as many rows as the queue is long, done for good, a repeat pass needs a
new id).
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
def _connect():
    """Open (and fail loudly on) the results worksheet.

    Cached per-process: one gspread client/session for the app's lifetime.
    Deliberately does NOT check/create the header row, that's cheap enough
    to redo on every call (see _worksheet), and caching it here would mean
    it only ever runs once per process. If someone manually clears the
    sheet (header included) mid-lifetime, a cached one-time check would
    never notice, appends would silently land in row 1 as if it were data,
    and every lookup after that would misread that data row as the header
    (this happened once; see git history).
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
        return sheet.sheet1
    except Exception as e:  # noqa: BLE001 - fail loudly per spec
        raise RuntimeError(
            f"Could not reach Google Sheet (key={sheet_key!r}). "
            f"Check sharing + secrets. Original error: {e}"
        ) from e


def _worksheet():
    """The results worksheet, with its header row verified/recreated on
    every call. Self-heals if the sheet is ever wiped clean mid-session;
    if it's wiped down to a non-empty, non-matching row 1 instead, fails
    loudly rather than silently misreading data as headers."""
    ws = _connect()
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


def _rows_for(curator_id: str) -> list[dict]:
    ws = _worksheet()
    records = ws.get_all_records()  # list[dict] keyed by header row
    return [r for r in records if str(r.get("curator_id")) == str(curator_id)]


def id_status(curator_id: str, total_items: int) -> tuple[str, set[tuple[str, int]]]:
    """Status of a curator_id: "not_found", "in_progress", or "completed".

    For "in_progress", also returns the (image_id, repeat_index) pairs
    already recorded, so the caller can resume from there. Empty set for
    the other two statuses.
    """
    rows = _rows_for(curator_id)
    if not rows:
        return "not_found", set()
    if len(rows) >= total_items:
        return "completed", set()

    done = set()
    for r in rows:
        image_id = r.get("image_id")
        try:
            repeat_index = int(r.get("repeat_index", 0))
        except (TypeError, ValueError):
            repeat_index = 0
        done.add((image_id, repeat_index))
    return "in_progress", done


def assign_new_id(candidate_fn, max_attempts: int = 30) -> str:
    """A fresh curator_id that has never been used before.

    `candidate_fn()` produces a random candidate string (see
    app.py:new_suggestion). Reads the sheet once for all curator_ids ever
    used, then retries candidates locally until one is unused, avoiding a
    sheet round-trip per attempt.

    Small race window between this check and the curator's first write is
    accepted at this project's scale (~10 curators); not worth the added
    complexity of reserving ids ahead of use.
    """
    ws = _worksheet()
    records = ws.get_all_records()
    used = {str(r.get("curator_id")) for r in records}

    for _ in range(max_attempts):
        candidate = candidate_fn()
        if candidate not in used:
            return candidate
    raise RuntimeError("Could not find an unused ID after many attempts.")
