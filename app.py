"""marbleness, expert fish-evaluation app.

Curators rate trout photos 0 (fario) - 1 (marmorata) on a slider. See
CLAUDE.md for full spec / data-integrity requirements this file implements.
"""

import random
import time
from pathlib import Path

import streamlit as st

import i18n
from i18n import t
from assignment import build_queue, list_image_ids
from storage import assign_new_id, append_result, id_status

APP_VERSION = "1.0"
IMAGE_DIR = Path("images")
N_REPEATS = 4
_N_IMAGES = len(list_image_ids(IMAGE_DIR))
TOTAL_ITEMS = _N_IMAGES + min(N_REPEATS, _N_IMAGES)  # mirrors build_queue's clamp

# Word lists for the assigned-id generator. A curator_id is a one-time,
# system-issued identifier, never freely chosen, this just makes it
# memorable instead of a raw uuid. Large enough combination space
# (20*67*90) that collisions are rare; storage.assign_new_id() still
# checks uniqueness against the sheet before handing one out.
_ADJECTIVES = [
    "brave", "calm", "clever", "curious", "eager", "gentle", "happy",
    "jolly", "kind", "lively", "mighty", "nimble", "proud", "quiet",
    "quick", "sunny", "swift", "witty", "bold", "bright",
]
# Fish names (from fish_names.txt), lowercased and underscore-joined for a
# valid id. Themed to match the survey, replaces a generic animal list.
_FISH_NAMES = [
    "trout", "salmon", "carp", "catfish", "pike", "perch", "zander",
    "pikeperch", "largemouth_bass", "sturgeon", "eel", "goldfish",
    "guppy", "betta", "siamese_fighting_fish", "angelfish", "piranha",
    "tilapia", "chub", "barbel", "tench", "grayling", "roach", "bream",
    "arowana", "discus", "tuna", "cod", "sea_bass", "gilt_head_bream",
    "sea_bream", "swordfish", "mackerel", "sardine", "anchovy", "shark",
    "sole", "flounder", "plaice", "halibut", "red_mullet", "grouper",
    "dentex", "snapper", "turbot", "monkfish", "anglerfish", "hake",
    "herring", "clownfish", "barracuda", "ray", "skate", "manta_ray",
    "moray_eel", "amberjack", "john_dory", "mahi_mahi", "dorado",
    "seahorse", "pufferfish", "blowfish", "flying_fish", "red_snapper",
    "lionfish", "parrotfish", "surgeonfish",
]

# Fixed bilingual title, not run through t(): @st.dialog's title argument
# is evaluated once at decoration time (module load), not per-render, so
# it can't reactively re-translate if the curator switches language later.
@st.dialog("Consent statement / Dichiarazione di consenso")
def show_consent_dialog():
    for key in (
        "consent_full_collect",
        "consent_full_not_collect",
        "consent_full_usage",
        "consent_full_id",
        "consent_full_voluntary",
    ):
        st.markdown(t(key))
    if st.button(t("consent_dialog_close_button")):
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
    return f"{random.choice(_ADJECTIVES)}_{random.choice(_FISH_NAMES)}_{random.randint(10, 99)}"


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

if "lang" not in st.session_state:
    st.session_state.lang = i18n.DEFAULT_LANGUAGE

# Fixed bilingual label, not run through t(): avoids a chicken-and-egg
# translation of the switcher that controls the translation.
_lang_col = st.columns([5, 2])[1]
with _lang_col:
    st.selectbox(
        "Language / Lingua",
        options=list(i18n.LANGUAGES.keys()),
        format_func=lambda code: i18n.LANGUAGES[code],
        key="lang",
        label_visibility="collapsed",
    )

st.title("marbleness")

if "stage" not in st.session_state:
    st.session_state.stage = "consent"

# 1. Consent + instructions -------------------------------------------------
if st.session_state.stage == "consent":
    st.header(t("consent_header"))
    st.markdown(t("consent_intro", total_items=TOTAL_ITEMS))

    st.divider()
    st.subheader(t("consent_data_header"))
    st.markdown(t("consent_summary"))
    if st.button(t("consent_read_full_button")):
        show_consent_dialog()

    agreed = st.checkbox(t("consent_agree_checkbox"), key="agreed")
    if st.button(t("consent_agree_button"), type="primary", disabled=not agreed):
        st.session_state.stage = "identify"
        st.rerun()
    st.stop()

# 2. Curator identification --------------------------------------------------
if st.session_state.stage == "identify":
    st.header(t("identify_header"))

    st.subheader(t("identify_new_subheader"))
    st.caption(t("identify_new_caption"))

    if "assigned_id" not in st.session_state:
        st.session_state.assigned_id = assign_new_id(new_suggestion)

    col1, col2 = st.columns([4, 1])
    with col1:
        st.code(st.session_state.assigned_id, language=None)  # has a built-in copy button
    with col2:
        if st.button(t("identify_new_button"), help=t("identify_new_button_help")):
            st.session_state.assigned_id = assign_new_id(new_suggestion)
            st.rerun()

    if st.button(t("identify_start_button"), type="primary"):
        # Freshly assigned by assign_new_id(), so guaranteed to have no
        # existing rows: skip the sheet lookup and start straight in.
        _start_queue(st.session_state.assigned_id, set())
        st.rerun()

    st.divider()
    st.subheader(t("identify_resume_subheader"))
    resume_input = st.text_input(t("identify_resume_input_label"), key="resume_id_input")

    if st.button(t("identify_resume_button")):
        candidate = resume_input.strip()
        if not candidate:
            st.warning(t("identify_resume_warning_empty"))
        else:
            status, done = id_status(candidate, TOTAL_ITEMS)
            if status == "in_progress":
                _start_queue(candidate, done)
                st.rerun()
            else:
                st.error(t("identify_resume_error_unknown"))
    st.stop()

# 3. Evaluation loop ----------------------------------------------------------
if st.session_state.stage == "evaluate":
    item = current_item()
    if item is None:
        st.session_state.stage = "complete"
        st.rerun()

    total = st.session_state.total_in_queue
    n_done = len(st.session_state.done)
    percent = round(n_done / total * 100) if total else 100

    st.progress(n_done / total if total else 1.0)
    st.caption(t(
        "evaluate_progress_caption",
        n=n_done + 1,
        total=total,
        percent=percent,
    ))

    image_bytes = load_image_bytes(item["image_id"])
    st.image(image_bytes, use_container_width=True)

    st.select_slider(
        t("evaluate_slider_label"),
        options=SLIDER_OPTIONS,
        key="slider_value",
        on_change=on_slider_change,
    )
    st.checkbox(
        t("evaluate_unsure_checkbox"),
        key="unsure",
        on_change=on_unsure_change,
    )

    can_advance = st.session_state.slider_touched or st.session_state.unsure
    if not can_advance:
        st.caption(t("evaluate_touch_hint"))

    # advance() must run as an on_click callback, not inline after the
    # button check: callbacks run *before* widgets are re-instantiated for
    # the next script run, which is the only point it's legal to reset
    # session_state.slider_value (the select_slider's own key). Doing it
    # inline here would hit StreamlitWidgetAlreadyInstantiatedError since
    # the slider widget already rendered earlier in this same run.
    st.button(t("evaluate_next_button"), type="primary", disabled=not can_advance, on_click=advance)
    st.stop()

# 4. Completion ---------------------------------------------------------------
if st.session_state.stage == "complete":
    st.header(t("complete_header"))
    st.markdown(t("complete_body"))
    st.stop()
