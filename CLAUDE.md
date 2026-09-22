# CLAUDE.md, marbleness: Expert Fish-Evaluation App

## What we are building

A public web app for the **marbleness** project. Fish biology experts ("curators")
look at trout photographs one at a time and estimate, on a continuous 0–1 slider,
how *marmorata* (marble trout, 1.0) vs *fario* (Atlantic brown trout, 0.0) the
fish appears. Their responses are the **human baseline** for a machine-learning
model that predicts the same value from images. This is a scientific measurement
instrument, data integrity matters more than features.

**Design:** ~10 curators, and **every curator rates the SAME 60 images**
(all-overlap design, for maximum inter-rater agreement measurement). The 60
images are already chosen and committed in the repo under `images/`.

## Repo layout (already partly present)

```
marbleness/
  images/            # the 60 shared .jpg photos, ALREADY HERE
  app.py             # you create
  assignment.py      # you create
  storage.py         # you create
  i18n.py            # you create (Italian/English UI strings)
  scripts/
    analyze.py       # you create (analysis)
    resize_images.py # you create (one-off image prep)
  requirements.txt
  .gitignore
  .streamlit/
    secrets.toml.example
  README.md
```

## Non-negotiable requirements (the reasons this app exists)

1. **Per-response persistence.** Write each rating to durable storage the instant
   the user advances, never batch to the end. A dropped session must cost at most
   the current image.

2. **Durable EXTERNAL storage for results.** Streamlit Community Cloud has an
   **ephemeral filesystem**, local files are wiped on restart/redeploy. Results
   must go to **Google Sheets** via `gspread` + a service account (primary plan).
   A local CSV may exist only as a redundant append-only backup, never the sole
   store. (Note: the *images* live in the repo and are fine there; only the
   *results* need external storage.)

3. **Everyone rates the same 60 images.** The queue for every curator is the
   contents of `images/`. There is NO per-user random subset and NO unique set.

4. **Assigned ID + resume.** `curator_id` is never freely chosen: it's
   system-assigned (see req. 9) and maps 1:1 to exactly one lifetime
   attempt at the survey. On login, a curator can enter a previously
   assigned id to resume: if it has an unfinished attempt (fewer rows than
   the queue is long), resume it (skip whatever it already has recorded,
   survives a closed tab/browser); if it's unknown or already finished,
   tell them so and point them at getting a new assigned id, do NOT start
   a new attempt under a typed id. Idempotent: a given (curator_id,
   image_id, repeat_index) is written at most once.

5. **Blinding, critical, and specific.** The photo filenames encode fish IDs
   (e.g. `Satr251804.jpg`) which map to genetic ground truth. The curator must
   NEVER see the filename. Implement by **loading the image bytes and passing
   them to `st.image()`** so no filename/path is exposed in the browser, page,
   or network request. Do NOT rename the files on disk, we need the real
   filename server-side to join responses back to qMar. Store the real
   `image_id` in results (server-side only); never render it.

6. **Randomized, per-curator order.** Present the 60 in an order seeded by
   `hash(curator_id)` so it is reproducible (a resumed attempt rebuilds the
   identical queue) but differs across curators (removes order/fatigue
   confounds on specific images).

7. **No mid-scale default anchor.** The slider must NOT pre-fill at 0.5 (it
   biases responses toward the hybrid middle, exactly what we care about).
   Require a deliberate interaction before "Next" is enabled (track a
   `slider_touched` flag via an `on_change` callback, or an explicit "estimate
   set" control). Provide an **"Unsure / can't tell"** checkbox as an
   independent flag, not a replacement for the score: if the curator set a
   slider value and then also checked Unsure, keep the value they set. Score
   is blank only when the slider was never touched at all.

8. **Intra-rater repeats.** Silently append a small number (config
   `N_REPEATS`, default 4) of the 60 images a second time, at random positions
   in that curator's queue, to measure within-rater consistency. So each
   curator sees 60 + N_REPEATS items. Repeats share the `image_id` but get a
   distinct `repeat_index`. Never reveal that repeats exist.

9. **System-assigned, unique curator IDs.** No free-text choice for a new
   attempt. The app generates a random human-readable id
   (adjective_fish_number) and checks it against every curator_id already
   in the sheet, retrying until one is unused, before handing it to the
   curator. That id is shown read-only (not editable) with a way to copy
   it and a way to reroll for a different one before starting.

10. **Italian + English, switchable at any point.** Curators are mostly
    Italian-speaking, so the app defaults to Italian with a switcher
    (`st.session_state.lang`) visible on every screen. Switching language
    must never reset progress (queue/cursor/curator_id/done), it only
    re-renders the same state in the other language. All UI strings live
    in `i18n.py`, not inline in `app.py`. Curator IDs, image filenames,
    and anything written to the results sheet are never translated.

## Data model

### Curator identification
No fixed roster and no free-text choice for a new id: the app assigns a
random human-readable id (adjective_fish_number, e.g. `clever_trout_42`),
checked unique against the sheet, shown read-only with a copy button and a
reroll button. To resume, a curator types in a previously assigned id; it
only works if that id has an unfinished attempt. No passwords, low-stakes,
internal.

### Results sheet (Google Sheet, one row appended per rating)
Columns: `timestamp_iso`, `curator_id`, `image_id`, `repeat_index`, `score`
(float 0–1, blank only if the slider was never touched), `unsure` (bool,
independent of score), `dwell_seconds` (time image was on screen),
`slider_touched` (bool), `queue_position`, `app_version`.

## Screens / flow

A language switcher (Italian/English, defaulting to Italian) is visible on
every screen, independent of the stage flow below.

1. **Consent + instructions.** Brief task explanation ("estimate how marble vs
   Atlantic this trout looks: 0 = pure Atlantic fario, 1 = pure marble
   marmorata; use the whole scale"), note that responses are recorded, and an
   "I agree, begin" button. Include any reference/calibration images if provided
   later (leave a clearly marked spot).
2. **Curator identification.** Two paths: (a) new here, get a system-assigned
   id (read-only, copyable, rerollable), press Start; (b) already started,
   type a previously assigned id, press Resume, works only if that id has
   an unfinished attempt (otherwise: error, get a new assigned id instead).
3. **Evaluation loop**, for each remaining item:
   - Progress bar `Image {n} of {total}` + percent complete (`n_done /
     total`). Deliberately no time estimate, that adds pressure.
   - The image, large, centered, `use_container_width=True`, served from bytes.
   - Slider 0.00–1.00 step 0.01, NO 0.5 default.
   - "Unsure / can't tell" checkbox.
   - "Next" disabled until slider touched or Unsure checked.
   - On Next: append row to sheet immediately, record dwell time, advance,
     `st.rerun()`.
4. **Completion screen.** Thank-you; make clear they can close the tab.

## Technical notes

- **Framework:** Streamlit. `app.py` + `storage.py` + `assignment.py` + `i18n.py`.
- **i18n.py:** `t(key, lang=None, **kwargs) -> str` looks up `key` in
  `lang` (or the live `st.session_state.lang` if omitted), formats any
  `**kwargs` placeholders. Two plain dicts (`"it"`/`"en"`), no external
  i18n library, the string set is small and has no pluralization
  complexity. A widget whose *label* changes with language needs an
  explicit `key=` (e.g. the consent checkbox, the resume-id text input),
  otherwise Streamlit treats the re-labeled widget as a new instance on
  language switch and silently drops its value.
- **assignment.py:** `build_queue(curator_id, image_dir, n_repeats) -> list[dict]`
  returning ordered items `{image_id, repeat_index, queue_position}`,
  deterministic from `hash(curator_id)`. Pure function, no I/O beyond listing
  `images/`.
- **storage.py:** `append_result(row: dict)`,
  `id_status(curator_id, total_items) -> (status, done)` where status is
  "not_found"/"in_progress"/"completed" and `done` is
  `set[(image_id, repeat_index)]`, and `assign_new_id(candidate_fn) -> str`
  (checks uniqueness against the sheet before handing one out), all
  implemented against Google Sheets with `gspread`. Keep the interface
  swappable so a Postgres backend (Supabase/Neon via `st.connection`) is a
  drop-in. Document both.
- **Auth to Sheets:** service-account JSON in **Streamlit secrets**
  (`st.secrets`), never committed. Share the Sheet with the service-account
  email. Sheet key also in secrets.
- **Idempotency:** `id_status` reports the curator's `done` set on load;
  guard the append so refreshes/re-submits don't double-write.
- **Images:** read from local `images/`. If any exceed ~1600px on the long edge,
  downsize for the web first, see `scripts/resize_images.py` (repo size +
  page-load). Serve via bytes (req. 5).
- **State:** `st.session_state` for in-session queue/cursor and per-image
  shown-at timestamps only. The sheet is the durable truth; never rely on
  session_state surviving refresh.
- **Fail loudly** if the Sheet is unreachable at startup, a hard error beats
  silent data loss.

## Deliverables

1. `app.py`, `storage.py`, `assignment.py`, `i18n.py` implementing all the above.
2. `scripts/resize_images.py`, one-off: downsize `images/*.jpg` to max 1600px
   long edge, ~85% quality, preserving filenames. Idempotent; skips already-small
   files. (Pillow.)
3. `scripts/analyze.py`, pulls the results sheet and computes: inter-rater
   reliability (ICC and Krippendorff's α) across all 60 images; per-curator
   bias/scale vs the cross-curator consensus; and intra-rater consistency from
   the repeated images. This is the scientific payoff of the all-overlap design,
   make it real, not a stub.
4. `requirements.txt` (streamlit, gspread, google-auth, pandas, pillow;
   pingouin or numpy for ICC).
5. `.gitignore` (secrets, service-account json, local backup data,
   `__pycache__`, venv).
6. `.streamlit/secrets.toml.example` showing required keys (no real secrets).
7. `README.md`: local run; create Google service account + share Sheet; set
   Streamlit Cloud secrets; run resize script; deploy; export/analyze results.

## Out of scope / do NOT do

- No login/passwords beyond the assigned curator_id + resume-by-id.
- No admin UI.
- No qMar or any genetic value anywhere the app can read it. The app knows only
  image bytes and the (hidden) filename it records.
- No batching writes to the end of the session.
- No committing secrets. (Committing the 60 images is fine and expected.)
- No cloud image storage, images are local this time.

## Style

Simple, readable, commented Python. Clarity over cleverness. Whole app well
under a few hundred lines.
