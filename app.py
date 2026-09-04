"""marbleness — expert fish-evaluation app.

Curators rate trout photos 0 (fario) - 1 (marmorata) on a slider. See
CLAUDE.md for full spec / data-integrity requirements this file implements.
"""

import csv
import time
from pathlib import Path

import streamlit as st

from assignment import build_queue
from storage import append_result, completed

APP_VERSION = "1.0"
IMAGE_DIR = Path("images")
CURATORS_CSV = Path("curators.csv")
N_REPEATS = 4
SECONDS_PER_IMAGE_ESTIMATE = 15

# Sentinel shown before the curator has touched the slider. Must NOT be a
# valid score, and must not render as a numeric position on the track
# (which is why we use a select_slider with this as the first option,
# rather than a regular slider defaulted to 0.0/0.5/1.0).
UNTOUCHED = "—"  # "—"
SLIDER_OPTIONS = [UNTOUCHED] + [round(i / 100, 2) for i in range(0, 101)]

st.set_page_config(page_title="marbleness", layout="centered")


# ---------------------------------------------------------------- helpers --

@st.cache_data
def load_curator_ids() -> list[str]:
    if not CURATORS_CSV.exists():
        raise RuntimeError(f"{CURATORS_CSV} not found.")
    with open(CURATORS_CSV, newline="") as f:
        rows = list(csv.DictReader(f))
    ids = [r["curator_id"].strip() for r in rows if r.get("curator_id", "").strip()]
    if not ids:
        raise RuntimeError(f"{CURATORS_CSV} has no curator_id values.")
    return ids


@st.cache_data
def load_image_bytes(image_id: str) -> bytes:
    """Load raw bytes server-side. Passing bytes (not a path) to st.image
    is what keeps the filename out of the browser/page/network request."""
    with open(IMAGE_DIR / image_id, "rb") as f:
        return f.read()


def on_slider_change():
    st.session_state.slider_touched = True


def on_unsure_change():
    # Toggling "unsure" also counts as a deliberate interaction.
    pass


def current_item():
    q = st.session_state.queue
    i = st.session_state.cursor
    return q[i] if i < len(q) else None


def reset_per_image_state():
    st.session_state.slider_touched = False
    st.session_state.slider_value = UNTOUCHED
    st.session_state.unsure = False
    st.session_state.shown_at = time.time()


def advance():
    item = current_item()
    score = st.session_state.slider_value
    unsure = st.session_state.unsure
    dwell = time.time() - st.session_state.shown_at

    row = {
        "curator_id": st.session_state.curator_id,
        "image_id": item["image_id"],
        "repeat_index": item["repeat_index"],
        "score": "" if unsure else float(score),
        "unsure": unsure,
        "dwell_seconds": round(dwell, 2),
        "slider_touched": st.session_state.slider_touched,
        "queue_position": item["queue_position"],
        "app_version": APP_VERSION,
    }
    append_result(row)

    st.session_state.done.add((item["image_id"], item["repeat_index"]))
    st.session_state.cursor += 1
    reset_per_image_state()


# ------------------------------------------------------------------ flow --

st.title("marbleness")

if "stage" not in st.session_state:
    st.session_state.stage = "consent"

# 1. Consent + instructions -------------------------------------------------
if st.session_state.stage == "consent":
    st.header("Before you begin")
    st.markdown(
        """
Thank you for helping evaluate trout photographs.

For each photo, estimate on a slider how the fish looks between two
extremes:

- **0.0** — pure Atlantic **fario** (brown trout)
- **1.0** — pure marble trout **marmorata**

Please use the whole scale — including the middle, if that's genuinely
your judgement. If a photo doesn't let you tell, check **"Unsure / can't
tell"** instead of guessing.

Your responses are recorded (including how long you spend on each photo)
and used as a scientific baseline for a machine-learning model. There are
no right answers we're checking you against — we want your honest,
independent estimate.

*(Reference / calibration images, if provided, would go here.)*
        """
    )
    if st.button("I agree, begin", type="primary"):
        st.session_state.stage = "identify"
        st.rerun()
    st.stop()

# 2. Curator identification --------------------------------------------------
if st.session_state.stage == "identify":
    st.header("Who are you?")
    curator_ids = load_curator_ids()
    choice = st.selectbox(
        "Select your curator ID", options=["— select —"] + curator_ids
    )
    if choice != "— select —" and st.button("Continue", type="primary"):
        st.session_state.curator_id = choice
        done = completed(choice)
        st.session_state.done = done

        queue = build_queue(choice, IMAGE_DIR, n_repeats=N_REPEATS)
        # Resume: skip anything already recorded for this curator.
        remaining = [
            item for item in queue
            if (item["image_id"], item["repeat_index"]) not in done
        ]
        st.session_state.queue = remaining
        st.session_state.total_in_queue = len(queue)
        st.session_state.cursor = 0
        reset_per_image_state()

        st.session_state.stage = "evaluate" if remaining else "complete"
        st.rerun()
    st.stop()

# 3. Evaluation loop ----------------------------------------------------------
if st.session_state.stage == "evaluate":
    item = current_item()
    if item is None:
        st.session_state.stage = "complete"
        st.rerun()

    total = st.session_state.total_in_queue
    n_done = len(st.session_state.done)
    remaining_n = total - n_done

    st.progress(n_done / total if total else 1.0)
    st.caption(
        f"Image {n_done + 1} of {total} "
        f"— about {remaining_n * SECONDS_PER_IMAGE_ESTIMATE // 60} min left"
    )

    image_bytes = load_image_bytes(item["image_id"])
    st.image(image_bytes, use_container_width=True)

    st.select_slider(
        "0 = pure fario · 1 = pure marmorata",
        options=SLIDER_OPTIONS,
        key="slider_value",
        on_change=on_slider_change,
    )
    st.checkbox(
        "Unsure / can't tell",
        key="unsure",
        on_change=on_unsure_change,
    )

    can_advance = st.session_state.slider_touched or st.session_state.unsure
    if not can_advance:
        st.caption("Move the slider (or check Unsure) to continue.")

    # advance() must run as an on_click callback, not inline after the
    # button check: callbacks run *before* widgets are re-instantiated for
    # the next script run, which is the only point it's legal to reset
    # session_state.slider_value (the select_slider's own key). Doing it
    # inline here would hit StreamlitWidgetAlreadyInstantiatedError since
    # the slider widget already rendered earlier in this same run.
    st.button("Next", type="primary", disabled=not can_advance, on_click=advance)
    st.stop()

# 4. Completion ---------------------------------------------------------------
if st.session_state.stage == "complete":
    st.header("All done — thank you!")
    st.markdown(
        "Your ratings have been recorded. You can safely close this tab."
    )
    st.stop()
