"""marbleness, expert fish-evaluation app.

Curators rate trout photos 0 (fario) - 1 (marmorata) on a slider. See
CLAUDE.md for full spec / data-integrity requirements this file implements.
"""

import html
import random
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from assignment import build_queue, list_image_ids
from storage import append_result, resume_or_new_session

APP_VERSION = "1.0"
IMAGE_DIR = Path("images")
N_REPEATS = 4
SECONDS_PER_IMAGE_ESTIMATE = 15
_N_IMAGES = len(list_image_ids(IMAGE_DIR))
TOTAL_ITEMS = _N_IMAGES + min(N_REPEATS, _N_IMAGES)  # mirrors build_queue's clamp

# Word lists for the suggested-id generator. Purely a convenience, the
# curator_id field is free text, this just saves people from typing their
# own. Large enough combination space (20*20*90) to rarely collide.
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
    "We store your ratings, under the ID you choose here, for machine-"
    "learning research. We don't collect anything else: no IP address, "
    "no location, no browser/device info, no name or email."
)

CONSENT_FULL_TEXT = """
### What we collect
- The ID you enter on the next screen (a pseudonym, you don't need to use your real name).
- Your estimate for each photo (the 0–1 slider position, or "unsure").
- How long each photo stays on screen before you move on.
- A timestamp for each response.

### What we do NOT collect
- No IP address, device, browser, or geographic location.
- No cookies or tracking beyond keeping your place in the survey.
- No name, email, or other identifying information.

### How your data is used
- Your ratings, together with other curators', become the human baseline
  used to train and evaluate a machine-learning model that predicts the
  same marmorata/fario score from photographs.
- Used only for this research project, never sold, shared with third
  parties, or repurposed beyond the marbleness project.

### About the ID you choose
- Because the ID is self-chosen and nothing else identifying is collected,
  your responses can't be linked back to you unless you pick an ID that
  identifies you personally. Using the suggested random ID avoids that.

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
    score = st.session_state.slider_value
    unsure = st.session_state.unsure
    dwell = time.time() - st.session_state.shown_at

    row = {
        "curator_id": st.session_state.curator_id,
        "session_id": st.session_state.session_id,
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

- **0.0**, pure Atlantic **fario** (brown trout)
- **1.0**, pure marble trout **marmorata**

Please use the whole scale including the middle, if that's genuinely
your judgement. If a photo doesn't let you tell, check **"Unsure / can't
tell"** instead of guessing.
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
    st.markdown(
        "This ID identifies your ratings, if you've started before, "
        "entering the same ID resumes where you left off. We've filled in "
        "a suggestion; keep it, edit it, or generate another."
    )

    if "curator_id_input" not in st.session_state:
        st.session_state.curator_id_input = new_suggestion()

    def _regenerate_suggestion():
        st.session_state.curator_id_input = new_suggestion()

    col1, col2, col3 = st.columns([5, 1, 1])
    with col1:
        st.text_input("Your ID", key="curator_id_input", label_visibility="collapsed")
    with col2:
        st.button("🔀 New", on_click=_regenerate_suggestion, help="Generate a different suggested ID")
    with col3:
        # st.markdown(unsafe_allow_html=True) strips event-handler attributes
        # like onclick (Streamlit sanitizes even "unsafe" HTML), so a real
        # <script> needs an actual embedded document: components.html, which
        # renders in an iframe that does execute scripts. Value goes into a
        # data-* attribute (HTML-escaped) rather than into the script text,
        # so a curator typing quotes (or "</script>") into the ID field
        # can't break out of the markup.
        copy_value_attr = html.escape(st.session_state.curator_id_input, quote=True)
        components.html(
            f"""
            <style>
              html, body {{ margin:0; padding:0; height:100%; }}
              .copy-wrap {{
                height:100%; box-sizing:border-box; display:flex;
                align-items:center; gap:6px; font-family:sans-serif;
              }}
            </style>
            <div class="copy-wrap">
              <button id="copy-btn" data-copy="{copy_value_attr}" title="Copy ID to clipboard"
                style="width:2.5rem;height:2.5rem;flex:none;border-radius:0.5rem;
                border:1px solid rgba(128,128,128,0.4);cursor:pointer;font-size:1.1rem;
                background:transparent;">📋</button>
              <span id="copy-feedback" style="font-size:0.8rem;color:#16a34a;opacity:0;
                transition:opacity 0.3s;white-space:nowrap;">Copied!</span>
            </div>
            <script>
              const btn = document.getElementById("copy-btn");
              const feedback = document.getElementById("copy-feedback");
              function flashCopied() {{
                feedback.style.opacity = "1";
                setTimeout(() => {{ feedback.style.opacity = "0"; }}, 1200);
              }}
              function fallbackCopy(text) {{
                const ta = document.createElement("textarea");
                ta.value = text;
                ta.style.position = "fixed";
                ta.style.opacity = "0";
                document.body.appendChild(ta);
                ta.focus();
                ta.select();
                try {{ document.execCommand("copy"); }} catch (e) {{}}
                document.body.removeChild(ta);
              }}
              btn.addEventListener("click", function () {{
                const text = btn.getAttribute("data-copy");
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                  navigator.clipboard.writeText(text).then(flashCopied).catch(function () {{
                    fallbackCopy(text);
                    flashCopied();
                  }});
                }} else {{
                  fallbackCopy(text);
                  flashCopied();
                }}
              }});
            </script>
            """,
            height=45,
        )

    entered = st.session_state.curator_id_input.strip()

    if st.button("Continue", type="primary", disabled=not entered):
        session_id, done = resume_or_new_session(entered, TOTAL_ITEMS)

        st.session_state.curator_id = entered
        st.session_state.session_id = session_id
        st.session_state.done = done

        queue = build_queue(session_id, IMAGE_DIR, n_repeats=N_REPEATS)
        # Resume: skip anything already recorded in this session.
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
