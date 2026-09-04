"""Deterministic per-session queue construction.

Pure function, no I/O beyond listing `images/`. Every session sees the SAME
60 images (all-overlap design) but in a different, reproducible order, with
a handful of hidden repeats inserted at random positions to measure
intra-rater consistency. Seeded by session_id (not curator_id) so that a
curator's second attempt, a new session, gets a fresh order rather than
replaying their first attempt's exact sequence.
"""

import hashlib
import random
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg"}

N_REPEATS_DEFAULT = 4


def _stable_seed(session_id: str) -> int:
    """Stable hash of session_id -> int seed.

    Builtin hash() is randomized per-process (PYTHONHASHSEED) for strings,
    so it would NOT be reproducible across app restarts. Use sha256 instead
    so a resumed session always rebuilds the identical queue.
    """
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def list_image_ids(image_dir: str | Path) -> list[str]:
    """Sorted list of image filenames (the image_id) in image_dir."""
    image_dir = Path(image_dir)
    files = [
        p.name for p in image_dir.iterdir()
        if p.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return sorted(files)


def build_queue(
    session_id: str,
    image_dir: str | Path,
    n_repeats: int = N_REPEATS_DEFAULT,
) -> list[dict]:
    """Build ordered queue for one session.

    Returns list of dicts: {image_id, repeat_index, queue_position}.
    - Every image_id from image_dir appears once with repeat_index=0.
    - n_repeats distinct image_ids (chosen without replacement) appear a
      second time with repeat_index=1, inserted at random positions.
    - Order (both the base shuffle and repeat insertion points) is
      deterministic per session_id, reproducible across runs/resumes.
    """
    image_ids = list_image_ids(image_dir)
    rng = random.Random(_stable_seed(session_id))

    base_order = image_ids[:]
    rng.shuffle(base_order)
    base_items = [{"image_id": img, "repeat_index": 0} for img in base_order]

    n_repeats = min(n_repeats, len(image_ids))
    repeated_ids = rng.sample(image_ids, n_repeats) if n_repeats else []
    repeat_items = [{"image_id": img, "repeat_index": 1} for img in repeated_ids]

    # Insert each repeat item at an independent random position in the
    # growing sequence, so repeats land throughout the queue, not clumped
    # at the end.
    queue = base_items[:]
    for item in repeat_items:
        pos = rng.randint(0, len(queue))
        queue.insert(pos, item)

    for i, item in enumerate(queue):
        item["queue_position"] = i

    return queue
