"""Pull the results Google Sheet and compute the scientific payoff of the
all-overlap design:

  1. Inter-rater reliability across all 60 images: ICC(2,1) (two-way
     random, absolute agreement) and Krippendorff's alpha (interval).
  2. Per-curator bias (offset) and scale (slope) vs the cross-curator
     consensus (leave-one-out mean of the other curators).
  3. Intra-rater consistency from the hidden repeated images (repeat_index
     0 vs 1): mean absolute difference and correlation per curator.

Usage:
    python scripts/analyze.py [--out report.txt]

Reads credentials the same way the app does, but from a local
.streamlit/secrets.toml (no Streamlit runtime required for this script).
"""

import argparse
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SECRETS_PATH = Path(".streamlit/secrets.toml")


# --------------------------------------------------------------- fetching --

def load_secrets() -> dict:
    if not SECRETS_PATH.exists():
        raise RuntimeError(
            f"{SECRETS_PATH} not found. Copy secrets.toml.example and fill it in."
        )
    with open(SECRETS_PATH, "rb") as f:
        return tomllib.load(f)


def fetch_results() -> pd.DataFrame:
    secrets = load_secrets()
    creds = Credentials.from_service_account_info(
        secrets["gcp_service_account"], scopes=SCOPES
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(secrets["sheet_key"])
    records = sheet.sheet1.get_all_records()
    df = pd.DataFrame(records)
    if df.empty:
        raise RuntimeError("Results sheet is empty — nothing to analyze yet.")

    df["repeat_index"] = pd.to_numeric(df["repeat_index"], errors="coerce").fillna(0).astype(int)
    df["score"] = pd.to_numeric(df["score"], errors="coerce")  # blank -> NaN
    df["unsure"] = df["unsure"].astype(str).str.lower().isin(["true", "1", "yes"])
    return df


# ------------------------------------------------------------ reliability --

def icc_2_1(matrix: pd.DataFrame) -> float:
    """ICC(2,1): two-way random effects, single rater, absolute agreement.

    matrix: rows = targets (images), columns = raters (curators), no
    missing values (complete cases only — see caller).
    """
    data = matrix.to_numpy(dtype=float)
    n, k = data.shape  # n targets, k raters
    if n < 2 or k < 2:
        return float("nan")

    grand_mean = data.mean()
    target_means = data.mean(axis=1)
    rater_means = data.mean(axis=0)

    sst = ((data - grand_mean) ** 2).sum()
    ssr = k * ((target_means - grand_mean) ** 2).sum()
    ssc = n * ((rater_means - grand_mean) ** 2).sum()
    sse = sst - ssr - ssc

    df_r, df_c, df_e = n - 1, k - 1, (n - 1) * (k - 1)
    msr = ssr / df_r
    msc = ssc / df_c
    mse = sse / df_e if df_e > 0 else float("nan")

    denom = msr + (k - 1) * mse + k * (msc - mse) / n
    if denom == 0:
        return float("nan")
    return (msr - mse) / denom


def krippendorff_alpha_interval(units: dict[str, list[float]]) -> float:
    """Krippendorff's alpha for interval-level data, metric delta(a,b)=(a-b)^2.

    `units` maps unit id (image_id) -> list of values from different raters.
    Handles missing data (unequal counts per unit) natively.
    """
    n = sum(len(v) for v in units.values())
    if n < 2:
        return float("nan")

    do_num = 0.0
    for values in units.values():
        m = len(values)
        if m < 2:
            continue
        arr = np.array(values, dtype=float)
        diffs = arr[:, None] - arr[None, :]
        ordered_sum = (diffs ** 2).sum()  # diagonal is 0, so this is already "i != j"
        do_num += ordered_sum / (m - 1)
    do = do_num / n

    pooled = np.concatenate([np.array(v, dtype=float) for v in units.values() if v])
    diffs = pooled[:, None] - pooled[None, :]
    ordered_sum_all = (diffs ** 2).sum()
    de = ordered_sum_all / (n * (n - 1))

    if de == 0:
        return float("nan")
    return 1 - do / de


def analyze_reliability(df: pd.DataFrame) -> str:
    lines = ["## Inter-rater reliability (across all 60 images, first rating only)\n"]

    main = df[(df["repeat_index"] == 0) & (~df["unsure"]) & df["score"].notna()]
    pivot = main.pivot_table(index="image_id", columns="curator_id", values="score")

    complete = pivot.dropna(axis=0, how="any")  # images every remaining curator rated
    complete = complete.dropna(axis=1, how="any")  # belt-and-suspenders

    n_images_total, n_curators_total = pivot.shape
    n_images_complete, n_curators_complete = complete.shape
    lines.append(
        f"Data so far: {n_images_total} images x {n_curators_total} curators "
        f"({main.shape[0]} ratings). Complete-case matrix used for ICC: "
        f"{n_images_complete} images x {n_curators_complete} curators.\n"
    )

    if n_images_complete >= 2 and n_curators_complete >= 2:
        icc = icc_2_1(complete)
        lines.append(f"ICC(2,1) [two-way random, absolute agreement]: **{icc:.3f}**")
    else:
        lines.append("ICC(2,1): not enough complete-case data yet.")

    units = {
        image_id: row.dropna().tolist()
        for image_id, row in pivot.iterrows()
    }
    alpha = krippendorff_alpha_interval(units)
    lines.append(f"Krippendorff's alpha (interval, uses all available data): **{alpha:.3f}**")

    n_unsure = df[(df["repeat_index"] == 0) & df["unsure"]].shape[0]
    lines.append(f"\n'Unsure' responses (excluded above): {n_unsure}")
    return "\n".join(lines)


# --------------------------------------------------------- per-curator bias

def analyze_bias(df: pd.DataFrame) -> str:
    lines = ["\n## Per-curator bias / scale vs cross-curator consensus\n"]
    main = df[(df["repeat_index"] == 0) & (~df["unsure"]) & df["score"].notna()]
    pivot = main.pivot_table(index="image_id", columns="curator_id", values="score")

    rows = []
    for curator in pivot.columns:
        own = pivot[curator].dropna()
        others = pivot.drop(columns=[curator])
        consensus = others.loc[own.index].mean(axis=1, skipna=True)
        paired = pd.concat([own, consensus], axis=1, keys=["own", "consensus"]).dropna()
        if len(paired) < 3:
            rows.append((curator, len(paired), None, None, None))
            continue
        # own = a + b*consensus  (least squares)
        b, a = np.polyfit(paired["consensus"], paired["own"], 1)
        r = paired["own"].corr(paired["consensus"])
        rows.append((curator, len(paired), a, b, r))

    lines.append(f"{'curator':<15}{'n':>5}{'bias(a)':>10}{'scale(b)':>10}{'r':>8}")
    for curator, n, a, b, r in rows:
        if a is None:
            lines.append(f"{curator:<15}{n:>5}{'--':>10}{'--':>10}{'--':>8}")
        else:
            lines.append(f"{curator:<15}{n:>5}{a:>10.3f}{b:>10.3f}{r:>8.3f}")
    lines.append(
        "\nbias(a): curator's average offset from consensus (own = a + b*consensus). "
        "scale(b): how much the curator stretches/compresses the 0-1 range vs "
        "everyone else. b=1,a=0 is perfect agreement with the group."
    )
    return "\n".join(lines)


# ------------------------------------------------------- intra-rater repeats

def analyze_repeats(df: pd.DataFrame) -> str:
    lines = ["\n## Intra-rater consistency (hidden repeated images)\n"]

    scored = df[(~df["unsure"]) & df["score"].notna()]
    first = scored[scored["repeat_index"] == 0][["curator_id", "image_id", "score"]]
    second = scored[scored["repeat_index"] == 1][["curator_id", "image_id", "score"]]
    paired = first.merge(second, on=["curator_id", "image_id"], suffixes=("_1", "_2"))

    if paired.empty:
        lines.append("No repeat pairs recorded yet.")
        return "\n".join(lines)

    paired["abs_diff"] = (paired["score_1"] - paired["score_2"]).abs()

    lines.append(f"{'curator':<15}{'n_repeats':>10}{'mean|Δ|':>10}{'r':>8}")
    for curator, grp in paired.groupby("curator_id"):
        r = grp["score_1"].corr(grp["score_2"]) if len(grp) >= 3 else float("nan")
        lines.append(
            f"{curator:<15}{len(grp):>10}{grp['abs_diff'].mean():>10.3f}{r:>8.3f}"
        )

    lines.append(
        f"\nOverall mean |first - repeat| across all curators/images: "
        f"{paired['abs_diff'].mean():.3f} (n={len(paired)} repeat pairs)"
    )
    return "\n".join(lines)


# --------------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None, help="write report to this file too")
    args = parser.parse_args()

    df = fetch_results()

    report = "\n".join(
        [
            "# marbleness — results analysis",
            f"\nTotal rows in sheet: {len(df)}\n",
            analyze_reliability(df),
            analyze_bias(df),
            analyze_repeats(df),
        ]
    )

    print(report)
    if args.out:
        args.out.write_text(report)
        print(f"\n(also written to {args.out})")


if __name__ == "__main__":
    main()
