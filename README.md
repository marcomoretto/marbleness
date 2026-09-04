# marbleness

Expert fish-evaluation app. Curators rate trout photos on a 0 (fario) – 1
(marmorata) slider; every curator rates the same 60 images (all-overlap
design). See [CLAUDE.md](CLAUDE.md) for the full spec and rationale.

## Repo layout

```
app.py               # Streamlit UI / flow
assignment.py         # deterministic per-curator queue (pure function)
storage.py             # Google Sheets results storage + local CSV backup
scripts/
  resize_images.py     # one-off: downsize images/*.jpg for the web
  analyze.py            # inter/intra-rater reliability analysis
images/                 # the 60 shared photos
curators.csv            # allowed curator_id dropdown values
.streamlit/secrets.toml.example
```

## Local run

```bash
# with uv (this repo's pyproject.toml is already set up for it)
uv sync
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then fill it in, see below
uv run streamlit run app.py

# or with plain pip
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run app.py
```

The app fails loudly on startup if it can't reach the Google Sheet — that's
intentional (silent data loss is worse than a crash).

## One-time setup: Google Sheet + service account

1. **Create a Google Sheet** for results. Row 1 will be auto-populated with
   the header the first time the app runs against it. Copy the sheet's key
   from its URL: `https://docs.google.com/spreadsheets/d/<SHEET_KEY>/edit`.
2. **Create a service account** in a Google Cloud project:
   - Cloud Console → IAM & Admin → Service Accounts → Create.
   - Enable the **Google Sheets API** and **Google Drive API** for the project.
   - Create a JSON key for the service account and download it.
3. **Share the Sheet** with the service account's `client_email` (Editor access).
4. **Fill in secrets**: copy `.streamlit/secrets.toml.example` to
   `.streamlit/secrets.toml`, paste the JSON key's fields into
   `[gcp_service_account]`, and set `sheet_key` to the Sheet's key.
   This file is gitignored — never commit it.

## Curators

Edit `curators.csv` to list your real curator IDs (one `curator_id` per
row). This becomes the login dropdown — no passwords, low-stakes/internal.

## Prep images

Images already live in `images/`. Before committing/deploying, downsize
any that exceed 1600px on the long edge (repo size + page load):

```bash
uv run python scripts/resize_images.py
```

Idempotent — safe to re-run; already-small images are skipped.

## Deploy (Streamlit Community Cloud)

1. Push this repo (images included, secrets excluded) to GitHub.
2. Create a new app on [share.streamlit.io](https://share.streamlit.io)
   pointing at `app.py`.
3. In the app's **Settings → Secrets**, paste the same contents as your
   local `.streamlit/secrets.toml`.
4. Deploy. The filesystem is ephemeral on Cloud — that's fine, because
   results are written straight to the Google Sheet on every advance, not
   to local disk. (A `results_backup.csv` will appear locally but is wiped
   on redeploy — it's a redundant convenience, never the source of truth.)

## Export / analyze results

Once curators have rated some images:

```bash
uv run python scripts/analyze.py --out report.txt
```

This pulls the live Sheet and reports:
- **Inter-rater reliability** across the 60 images: ICC(2,1) and
  Krippendorff's alpha (interval).
- **Per-curator bias/scale** vs the cross-curator consensus (leave-one-out
  mean of the other curators), via a simple linear fit.
- **Intra-rater consistency** from the hidden repeated images (first vs.
  repeat rating): mean absolute difference and correlation per curator.

Run it any time — it works on partial data and reports how much it has.
