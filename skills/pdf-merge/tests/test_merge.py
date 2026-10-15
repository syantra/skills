# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdfium2==5.14.0", "pillow==12.3.0", "pypdf==6.20.1"]
# ///
"""Offline check for pdf_merge.py: page order, sizes, lossless images, the guards.

Run: uv run skills/pdf-merge/tests/test_merge.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image
from pypdf import PdfReader, PdfWriter

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pdf_merge.py"


def merge(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def pdf(path, *sizes):
    doc = pdfium.PdfDocument.new()
    for w, h in sizes:
        doc.new_page(w, h)
    doc.save(path)


def sizes(path):
    return [tuple(round(x) for x in p.get_size()) for p in pdfium.PdfDocument(path)]


def image_obj(path, i):
    return next(pdfium.PdfDocument(path)[i].get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE]))


with tempfile.TemporaryDirectory() as t:
    tmp = Path(t)
    pdf(tmp / "a.pdf", (612, 792), (300, 400))
    Image.new("RGB", (300, 200), (0, 128, 255)).save(tmp / "photo.jpg", dpi=(150, 150))
    noise = Image.frombytes("RGB", (64, 32), os.urandom(64 * 32 * 3))
    noise.save(tmp / "noise.png")
    clear = Image.new("RGBA", (100, 50), (255, 0, 0, 255))
    clear.paste((0, 0, 0, 0), (50, 0, 100, 50))
    clear.save(tmp / "clear.png")
    scans = tmp / "scans"
    scans.mkdir()
    Image.new("RGB", (20, 20)).save(scans / "2.png")
    Image.new("RGB", (30, 30)).save(scans / "10.png")
    Image.new("L", (40, 10)).save(scans / "11.tif", save_all=True, append_images=[Image.new("L", (40, 10))])
    (scans / "notes.txt").write_text("x")
    (scans / ".DS_Store").write_text("x")

    # order and sizes: PDF pages as they are, images from their DPI (72 without), folder in number order, TIFF per frame
    out = tmp / "out" / "merged.pdf"
    r = merge(out, tmp / "a.pdf", tmp / "photo.jpg", tmp / "noise.png", tmp / "clear.png", scans)
    assert r.returncode == 0, r.stderr
    assert sizes(out) == [(612, 792), (300, 400), (144, 96), (64, 32), (100, 50), (20, 20), (30, 30), (40, 10), (40, 10)], sizes(out)
    assert "skip" in r.stdout and "notes.txt" in r.stdout and ".DS_Store" not in r.stdout, r.stdout
    assert "9 pages" in r.stdout and not out.with_name("merged.pdf.part").exists()

    # JPEG byte for byte, PNG pixel for pixel, a transparent area white
    assert bytes(image_obj(out, 2).get_data(decode_simple=False)) == (tmp / "photo.jpg").read_bytes()
    assert image_obj(out, 3).get_bitmap().to_pil().convert("RGB").tobytes() == noise.tobytes()
    page = pdfium.PdfDocument(out)[4].render(scale=1).to_pil()
    assert page.getpixel((25, 25)) == (255, 0, 0) and page.getpixel((75, 25)) == (255, 255, 255)

    # a phone JPEG turned by EXIF: the page stands upright, the left half of the stored image on top
    side = Image.new("RGB", (40, 20), (255, 0, 0))
    side.paste((0, 0, 255), (20, 0, 40, 20))
    exif = Image.Exif()
    exif[0x0112] = 6
    side.save(tmp / "turned.jpg", exif=exif, quality=95)
    r = merge(tmp / "turned.pdf", tmp / "turned.jpg")
    assert r.returncode == 0 and sizes(tmp / "turned.pdf") == [(20, 40)], (r.stderr, sizes(tmp / "turned.pdf"))
    page = pdfium.PdfDocument(tmp / "turned.pdf")[0].render(scale=1).to_pil()
    top, bottom = page.getpixel((10, 5)), page.getpixel((10, 35))
    assert top[0] > 200 > top[2] and bottom[2] > 200 > bottom[0], (top, bottom)

    # past the 200-inch limit every image page shrinks by one factor; PDF pages do not
    Image.new("L", (100, 30000)).save(tmp / "tall.png")
    Image.new("L", (50, 50)).save(tmp / "small.png")
    pdf(tmp / "wide.pdf", (15000, 100))
    r = merge(tmp / "tall.pdf", tmp / "tall.png", tmp / "small.png", tmp / "wide.pdf")
    assert r.returncode == 0 and sizes(tmp / "tall.pdf") == [(48, 14400), (24, 24), (15000, 100)], sizes(tmp / "tall.pdf")
    assert "48%" in r.stdout

    # a PDF locked for editing only opens; one that needs a password to open stops the run
    for name, user in (("owner.pdf", ""), ("locked.pdf", "pw")):
        w = PdfWriter(clone_from=PdfReader(tmp / "a.pdf"))
        w.encrypt(user_password=user, owner_password="owner", algorithm="RC4-128")
        w.write(tmp / name)
    r = merge(tmp / "owner-out.pdf", tmp / "owner.pdf")
    assert r.returncode == 0 and len(sizes(tmp / "owner-out.pdf")) == 2, r.stderr
    r = merge(tmp / "locked-out.pdf", tmp / "a.pdf", tmp / "locked.pdf")
    assert r.returncode == 1 and "locked.pdf" in r.stderr and not (tmp / "locked-out.pdf").exists(), r.stderr

    # never over an input; an existing OUT only with --force
    before = (tmp / "a.pdf").read_bytes()
    r = merge(tmp / "a.pdf", tmp / "a.pdf", tmp / "photo.jpg")
    assert r.returncode == 1 and "one of the inputs" in r.stderr and (tmp / "a.pdf").read_bytes() == before
    r = merge(out, tmp / "photo.jpg")
    assert r.returncode == 1 and "--force" in r.stderr and len(sizes(out)) == 9
    r = merge(out, tmp / "photo.jpg", "--force")
    assert r.returncode == 0 and len(sizes(out)) == 1, r.stderr

    # inputs that cannot work
    assert merge(tmp / "x.pdf", tmp / "missing.pdf").stderr.startswith("error: not found")
    assert "not a PDF" in merge(tmp / "x.pdf", scans / "notes.txt").stderr
    (tmp / "empty").mkdir()
    assert "no PDFs or images" in merge(tmp / "x.pdf", tmp / "empty").stderr
    (tmp / "bad.png").write_text("not an image")
    r = merge(tmp / "x.pdf", tmp / "bad.png")
    assert r.returncode == 1 and "cannot read" in r.stderr and "bad.png" in r.stderr, r.stderr

print("ok")
