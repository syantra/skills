# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdfium2==5.14.0", "pillow==12.3.0"]
# ///
"""Merge PDFs and images into one PDF, pages in the order the inputs are given.

  uv run pdf_merge.py OUT.pdf INPUT... [--force]

An INPUT is a file or a folder. A folder adds the PDFs and images directly in it, sorted by
name with numbers in order (2 before 10); its subfolders and other files are skipped.
PDF pages keep their size. Each image becomes a page of its own shape, sized from its DPI
(72 when it has none); a multi-page TIFF gives one page per frame. When the largest image
page would pass the 200-inch PDF limit, every image page shrinks by the same factor, so
images keep their sizes relative to each other. JPEGs go in byte for byte, other images
lossless. Never writes over an input; replaces an existing OUT only with --force.
"""
import argparse
import os
import re
import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps, ImageSequence

IMAGES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
MAX_PT = 14400  # 200 inches, the largest page Acrobat opens
ORIENTATION = 0x0112  # EXIF tag; 5-8 turn the image a quarter


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def natural(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


def supported(p):
    return p.suffix.lower() == ".pdf" or p.suffix.lower() in IMAGES


def expand(inputs):
    files, skipped = [], []
    for a in inputs:
        p = Path(a)
        if p.is_dir():
            for f in sorted((f for f in p.iterdir() if not f.name.startswith(".")), key=natural):
                (files if f.is_file() and supported(f) else skipped).append(f)
        elif not p.exists():
            fail(f"not found: {a}")
        elif not supported(p):
            fail(f"not a PDF or a {', '.join(sorted(IMAGES))} image: {a}")
        else:
            files.append(p)
    return files, skipped


def frames(path):
    """Each page an image file gives: (frame, width in pt, height in pt), before any shrink."""
    im = Image.open(path)
    for frame in ImageSequence.Iterator(im) if im.format == "TIFF" else [im]:
        dx, dy = frame.info.get("dpi") or (72, 72)
        if not (dx >= 10 and dy >= 10):  # 0 or 1 means unset (Pillow writes TIFFs at 1)
            dx = dy = 72
        w, h = frame.size
        if frame.getexif().get(ORIENTATION, 1) > 4:
            w, h, dx, dy = h, w, dy, dx
        yield frame, w * 72 / dx, h * 72 / dy


def add_image(doc, path, frame, w, h):
    obj = pdfium.PdfImage.new(doc)
    if frame.format == "JPEG" and frame.mode in ("RGB", "L") and frame.getexif().get(ORIENTATION, 1) == 1:
        obj.load_jpeg(path, inline=False)  # the file's own bytes, no re-encode
    else:
        # ponytail: a rotated phone JPEG goes in lossless but several times its file size; place it with a rotated matrix if size matters
        frame = ImageOps.exif_transpose(frame)
        if frame.mode not in ("RGB", "RGBA", "L"):
            frame = frame.convert("RGBA" if frame.has_transparency_data else "RGB")
        obj.set_bitmap(pdfium.PdfBitmap.from_pil(frame))
    obj.set_matrix(pdfium.PdfMatrix().scale(w, h))
    page = doc.new_page(w, h)
    page.insert_obj(obj)
    page.gen_content()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", help="the PDF to write")
    ap.add_argument("inputs", nargs="+", help="PDFs, images and folders, in page order")
    ap.add_argument("--force", action="store_true", help="replace OUT when it exists")
    a = ap.parse_args()
    out = Path(a.out)
    files, skipped = expand(a.inputs)
    if not files:
        fail("no PDFs or images in the inputs")
    if out.resolve() in {f.resolve() for f in files}:
        fail(f"{out} is one of the inputs")
    if out.exists() and not a.force:
        fail(f"{out} exists; pass --force to replace it")

    sides = []
    for f in files:
        if f.suffix.lower() in IMAGES:
            try:
                sides += [s for _, w, h in frames(f) for s in (w, h)]
            except OSError as e:
                fail(f"cannot read {f}: {e}")
    k = min(1, MAX_PT / max(sides, default=1))

    doc = pdfium.PdfDocument.new()
    for f in files:
        before = len(doc)
        try:
            if f.suffix.lower() == ".pdf":
                doc.import_pages(pdfium.PdfDocument(f))
            else:
                for frame, w, h in frames(f):
                    add_image(doc, f, frame, w * k, h * k)
        except (OSError, pdfium.PdfiumError) as e:
            fail(f"cannot read {f}: {e}")
        print(f"{len(doc) - before:5d}  {f}")
    for f in skipped:
        print(f" skip  {f}")
    if k < 1:
        print(f"image pages shrunk to {k:.0%} to stay under the 200-inch page limit")
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(out.name + ".part")
    doc.save(part)
    os.replace(part, out)
    print(f"{len(doc)} pages -> {out}")


if __name__ == "__main__":
    main()
