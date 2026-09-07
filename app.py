"""marbleness, expert fish-evaluation app.

Curators rate trout photos 0 (fario) - 1 (marmorata) on a slider. See
CLAUDE.md for full spec / data-integrity requirements this file implements.
"""

import random
import time
from pathlib import Path

import streamlit as st

from assignment import build_queue, list_image_ids
from storage import assign_new_id, append_result, id_status

APP_VERSION = "1.0"
IMAGE_DIR = Path("images")
N_REPEATS = 4
SECONDS_PER_IMAGE_ESTIMATE = 15
_N_IMAGES = len(list_image_ids(IMAGE_DIR))
TOTAL_ITEMS = _N_IMAGES + min(N_REPEATS, _N_IMAGES)  # mirrors build_queue's clamp

# Word lists for the assigned-id generator. A curator_id is a one-time,
# system-issued identifier, never freely chosen, this just makes it
# memorable instead of a raw uuid. Large enough combination space
# (20*20*90) that collisions are rare; storage.assign_new_id() still
# checks uniqueness against the sheet before handing one out.
_ADJECTIVES = [
    "brave", "calm", "clever", "curious", "eager", "gentle", "happy",
    "jolly", "kind", "lively", "mighty", "nimble", "proud", "quiet",
    "quick", "sunny", "swift", "witty", "bold", "bright",
]
_ANIMALS = [
    "dolphin", "falcon", "otter", "panther", "heron", "lynx", "badger",
    "raven", "marlin", "koala", "gecko", "ibis", "puffin", "wombat",
    "tiger", "salmon", "osprey", "viper", "hare", "owl",
]

CONSENT_SUMMARY = (
    "We store your ratings, under an ID assigned to you, to evaluate how "
    "well a machine-learning model matches human judgment. We don't collect "
    "anything else: no IP address, no location, no browser/device info, no "
    "name or email."
)

CONSENT_FULL_TEXT = """
### What we collect
- The ID assigned to you when you start (not linked to your name or anything else).
- Your estimate for each photo (the 0-1 slider position, or "unsure").
- How long each photo stays on screen before you move on.
- A timestamp for each response.

### What we do NOT collect
- No IP address, device, browser, or geographic location.
- No cookies or tracking beyond keeping your place in the survey.
- No name, email, or other identifying information.

### How your data is used
- Your ratings, together with other curators', are used to evaluate how
  closely a machine-learning model's predictions match human judgment.
  They are not used to train that model.
- Used only for this research project, never sold, shared with third
  parties, or repurposed beyond the marbleness project.

### About your ID
- You're assigned a random ID (e.g. `clever_otter_42`) when you start; it
  isn't linked to your name or anything else. Keep note of it, you'll need
  it to resume if you leave partway through. Once you finish all photos
  under an ID, that ID is done, a repeat pass needs a freshly assigned one.

### Participation is voluntary
- You can stop at any time by closing the tab. Anything already submitted
  stays recorded; nothing further is collected after you leave.
"""


@st.dialog("Full consent statement")
def show_consent_dialog():
    st.markdown(CONSENT_FULL_TEXT)
    if st.button("Close"):
        st.rerun()


# Sentinel shown before the curator has touched the slider. Must NOT be a
# valid score, and must not render as a numeric position on the track
# (which is why we use a select_slider with this as the first option,
# rather than a regular slider defaulted to 0.0/0.5/1.0).
UNTOUCHED = ","
SLIDER_OPTIONS = [UNTOUCHED] + [round(i / 100, 2) for i in range(0, 101)]

st.set_page_config(page_title="marbleness", layout="centered")


# ---------------------------------------------------------------- helpers --

def new_suggestion() -> str:
    return f"{random.choice(_ADJECTIVES)}_{random.choice(_ANIMALS)}_{random.randint(10, 99)}"


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
    slider_value = st.session_state.slider_value
    # Score and "unsure" are independent: if the curator set a value and
    # then also checked Unsure, we still keep the value they set. Score is
    # blank only if the slider was never touched at all.
    has_score = slider_value != UNTOUCHED
    unsure = st.session_state.unsure
    dwell = time.time() - st.session_state.shown_at

    row = {
        "curator_id": st.session_state.curator_id,
        "image_id": item["image_id"],
        "repeat_index": item["repeat_index"],
        "score": float(slider_value) if has_score else "",
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


def _start_queue(curator_id: str, done: set[tuple[str, int]]) -> None:
    """Shared setup for both the new-id and resume paths."""
    st.session_state.curator_id = curator_id
    st.session_state.done = done

    queue = build_queue(curator_id, IMAGE_DIR, n_repeats=N_REPEATS)
    remaining = [
        item for item in queue
        if (item["image_id"], item["repeat_index"]) not in done
    ]
    st.session_state.queue = remaining
    st.session_state.total_in_queue = len(queue)
    st.session_state.cursor = 0
    reset_per_image_state()

    st.session_state.stage = "evaluate" if remaining else "complete"


# ------------------------------------------------------------------ flow --

st.title("marbleness")

if "stage" not in st.session_state:
    st.session_state.stage = "consent"

# 1. Consent + instructions -------------------------------------------------
if st.session_state.stage == "consent":
    st.header("Before you begin")
    st.markdown(
        f"""
Thank you for helping evaluate trout photographs.

For each photo, estimate on a slider how the fish looks between two
extremes:

- **0.0**, pure Atlantic **fario** (brown trout)
- **1.0**, pure marble trout **marmorata**

Please use the whole scale, including the middle, if that's genuinely your
judgement. You will be seeing {TOTAL_ITEMS} images uniformly distributed
across the entire scale. If a photo doesn't let you tell, check **"Unsure
/ can't tell"** instead of guessing.
"""
    )

    st.divider()
    st.subheader("Data & consent")
    st.markdown(CONSENT_SUMMARY)
    if st.button("📄 Read the full statement"):
        show_consent_dialog()

    agreed = st.checkbox("I have read and agree to the statement above.")
    if st.button("I agree, begin", type="primary", disabled=not agreed):
        st.session_state.stage = "identify"
        st.rerun()
    st.stop()

# 2. Curator identification --------------------------------------------------
if st.session_state.stage == "identify":
    st.header("Who are you?")

    st.subheader("New here?")
    st.caption(
        "We assign you a unique ID, you can't pick your own. Keep note of "
        "it: you'll need it to resume if you leave partway through."
    )

    if "assigned_id" not in st.session_state:
        st.session_state.assigned_id = assign_new_id(new_suggestion)

    col1, col2 = st.columns([4, 1])
    with col1:
        st.code(st.session_state.assigned_id, language=None)  # has a built-in copy button
    with col2:
        if st.button("🔀 New", help="Get a different assigned ID"):
            st.session_state.assigned_id = assign_new_id(new_suggestion)
            st.rerun()

    if st.button("Start with this ID", type="primary"):
        # Freshly assigned by assign_new_id(), so guaranteed to have no
        # existing rows: skip the sheet lookup and start straight in.
        _start_queue(st.session_state.assigned_id, set())
        st.rerun()

    st.divider()
    st.subheader("Already started?")
    resume_input = st.text_input("Enter your assigned ID to resume")

    if st.button("Resume"):
        candidate = resume_input.strip()
        if not candidate:
            st.warning("Enter an ID first.")
        else:
            status, done = id_status(candidate, TOTAL_ITEMS)
            if status == "in_progress":
                _start_queue(candidate, done)
                st.rerun()
            else:
                st.error(
                    "That ID doesn't exist or has already finished. "
                    "Start a new session with a freshly assigned ID above."
                )
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
        f"Image {n_done + 1} of {total}, "
        f"about {remaining_n * SECONDS_PER_IMAGE_ESTIMATE // 60} min left"
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
    st.header("All done, thank you!")
    st.markdown(
        "Your ratings have been recorded. You can safely close this tab."
    )
    st.stop()
