"""One-off: downsize images/*.jpg to max 1600px on the long edge, ~85%
quality, preserving filenames in place. Idempotent, skips files already
within the size limit. Run once before committing / redeploying.

Usage:
    python scripts/resize_images.py [image_dir]
"""

import sys
from pathlib import Path

from PIL import Image

MAX_LONG_EDGE = 1600
JPEG_QUALITY = 85


def resize_in_place(image_dir: Path) -> None:
    jpgs = sorted(image_dir.glob("*.jpg")) + sorted(image_dir.glob("*.jpeg"))
    if not jpgs:
        print(f"No .jpg/.jpeg files found in {image_dir}")
        return

    resized, skipped = 0, 0
    for path in jpgs:
        with Image.open(path) as img:
            long_edge = max(img.size)
            if long_edge <= MAX_LONG_EDGE:
                skipped += 1
                continue

            scale = MAX_LONG_EDGE / long_edge
            new_size = (round(img.width * scale), round(img.height * scale))
            img = img.convert("RGB")  # drop alpha/CMYK before re-saving JPEG
            img = img.resize(new_size, Image.LANCZOS)
            img.save(path, "JPEG", quality=JPEG_QUALITY, optimize=True)
            resized += 1
            print(f"resized {path.name}: long edge {long_edge} -> {MAX_LONG_EDGE}")

    print(f"Done. resized={resized} skipped(already small)={skipped}")


if __name__ == "__main__":
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("images")
    resize_in_place(directory)
