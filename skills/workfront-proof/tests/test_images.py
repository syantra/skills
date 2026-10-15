# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdfium2==5.14.0", "pillow==12.3.0", "pyobjc-framework-Vision==12.2.2; sys_platform == 'darwin'"]
# ///
"""Offline check for wfproof.images: markup -> pixel math, rendering sizes, label strip detection, colour names.

Run: uv run tests/test_images.py
"""
import ctypes
import importlib
import io
import sys
import tempfile
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as raw
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from wfproof import api, files, images

pages = importlib.import_module("wfproof.cmd.pages")

# A rectangle: points are relative to the page centre, scaled by PHQSCALE (4), y pointing down.
c1 = {"page": 1, "metadata": {"pageSizes": {"1": {"WIDTH": 9215, "HEIGHT": 5397, "PHQSCALE": 4}}},
      "drawings": [{"type": "RECTANGLE", "points": [{"x": 506.125, "y": -145.625}, {"x": 706.125, "y": -26.625}]}]}
assert images.markups(c1) == (9215, 5397, [("RECTANGLE", 6632.0, 2116.0, 7432.0, 2592.0)])
pin = {"page": 2, "metadata": {"pageSizes": {"2": {"WIDTH": 400, "HEIGHT": 800, "PHQSCALE": 1}}}, "drawings": [], "pinPoint": {"x": 10, "y": -20}}
assert images.markups(pin) == (400, 800, [("PIN", 210.0, 380.0, 210.0, 380.0)])
# Multi-page comment: only its first page's drawing is boxed.
size = {"WIDTH": 400, "HEIGHT": 800, "PHQSCALE": 1}
multi = {"page": 2, "pages": [2, 3], "metadata": {"pageSizes": {"2": size, "3": size}},
         "drawings": [{"type": "RECTANGLE", "page": 2, "points": [{"x": 0, "y": 0}]}, {"type": "RECTANGLE", "page": 3, "points": [{"x": 9, "y": 9}]}]}
assert images.markups(multi)[2] == [("RECTANGLE", 200.0, 400.0, 200.0, 400.0)]
# A line keeps its direction (start to end), so an arrow's tip is known; bbox() covers it either way.
up = {"page": 1, "metadata": {"pageSizes": {"1": size}}, "drawings": [{"type": "ARROW", "points": [{"x": 100, "y": 100}, {"x": -100, "y": -100}]}]}
assert images.markups(up)[2] == [("ARROW", 300.0, 500.0, 100.0, 300.0)]
assert images.bbox([("ARROW", 300.0, 500.0, 100.0, 300.0), ("PIN", 50.0, 50.0, 50.0, 50.0)]) == (50.0, 50.0, 300.0, 500.0)

# Render a region of a 100x200pt PDF page shown in the viewer as 400x800px.
with tempfile.TemporaryDirectory() as d:
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(100, 200)
    path = Path(d) / "p.pdf"
    pdf.save(path)
    assert images.render(path, 0, "application/pdf", 400, 800, (100, 200, 300, 600), [("RECTANGLE", 150, 250, 250, 550)]).size == (200, 400)
    assert images.render(path, 0, "application/pdf", 400, 800, (0, 0, 400, 3200), []).size == (200, 1600)  # capped at MAX_PX
    # A line is drawn along its path, not boxed: red at its midpoint, white where a box's corner would be, a dot at an arrow's tip.
    img = images.render(path, 0, "application/pdf", 400, 800, (0, 0, 400, 800), [("ARROW", 100, 100, 300, 300)]).convert("RGB")
    assert (img.getpixel((200, 200)), img.getpixel((100, 300)), img.getpixel((306, 300))) == ((255, 0, 0), (255, 255, 255), (255, 0, 0))
    # A CMYK JPEG and a grey PNG still get red marks and save as PNG.
    for mode, name in (("CMYK", "c.jpg"), ("L", "g.png")):
        Image.new(mode, (400, 800), "white").save(Path(d) / name)
        img = images.render(Path(d) / name, 0, "image", 400, 800, (0, 0, 400, 800), [("RECTANGLE", 100, 100, 300, 300)])
        img.save(io.BytesIO(), "PNG")
        assert img.getpixel((100, 200)) == (255, 0, 0), (mode, img.mode)
    # A screenshot embedded with more pixels than its page has points is sliced at the screenshot's sharpness, not one px per point.
    shot = pdfium.PdfDocument.new()
    page = shot.new_page(360, 750)
    pic = pdfium.PdfImage.new(shot)
    pic.set_bitmap(pdfium.PdfBitmap.from_pil(Image.new("RGB", (1440, 3000), "white")))
    pic.set_matrix(pdfium.PdfMatrix().scale(360, 750))
    page.insert_obj(pic)
    page.gen_content()
    shot.save(Path(d) / "shot.pdf")
    assert Image.open(images.page_slices(Path(d) / "shot.pdf", 0, "application/pdf", Path(d) / "page")[0][0]).width == images.SLICE_W
    # Text under a markup: what a strikethrough crosses (a zero-height box), and only the words at an arrow's tip, not the line it starts on.
    page = pdf.new_page(100, 200)
    for words, y in (("alpha beta", 150), ("gamma delta", 120)):
        t = raw.FPDFPageObj_NewTextObj(pdf.raw, b"Helvetica", 10)
        raw.FPDFText_SetText(t, ctypes.cast(ctypes.c_char_p((words + "\0").encode("utf-16-le")), raw.FPDF_WIDESTRING))
        raw.FPDFPageObj_Transform(t, 1, 0, 0, 1, 10, y)
        raw.FPDFPage_InsertObject(page.raw, t)
    raw.FPDFPage_GenerateContent(page.raw)
    pdf.save(path)
    assert [images.text_in_box(path, 1, "application/pdf", 400, [m]) for m in (("LINE", 40, 190, 130, 190), ("ARROW", 150, 180, 60, 310))] == ["alpha", "gamma"]

# Label strip: a white band with one short centred line of dark text above the page, at 2x.
with tempfile.TemporaryDirectory() as d:
    im, font = Image.new("RGB", (800, 600), "white"), ImageFont.load_default(20)
    draw = ImageDraw.Draw(im)
    draw.text((400, 24), "0.0 Home", fill="#333333", font=font, anchor="mm")
    _, top, _, bottom = draw.textbbox((400, 24), "0.0 Home", font=font, anchor="mm")
    band = top + bottom  # the text sits centred in its band
    draw.rectangle((0, band, 800, 600), fill="#1f0f3f")
    path = Path(d) / "s.png"
    im.save(path)
    px, box = images.capture(path, 0, "image/png")
    assert (px, box) == ([800, 600], (0, 0, 800, 600))
    strip = images.label_strip(path, 0, "image/png", px, box, 2)
    assert abs(strip[0] - band) <= 1 and strip[1:3] == ((255, 255, 255), (51, 51, 51)), strip[:3]
    assert images.ocr(strip[3]) == ("0.0 Home" if sys.platform == "darwin" else None)
    draw.rectangle((0, band, 800, band + 32), fill="white")  # the page's own blank top, in the strip's colour: not part of the strip
    im.save(path)
    assert abs(images.label_strip(path, 0, "image/png", px, box, 2)[0] - band) <= 1
    draw.rectangle((0, 0, 800, band), fill="white")
    draw.text((20, 24), "AX1 - Home", fill="#333333", font=font, anchor="lm")  # alignment and wording do not matter
    im.save(path)
    strip = images.label_strip(path, 0, "image/png", px, box, 2)
    assert abs(strip[0] - band) <= 1 and images.ocr(strip[3]) == ("AX1 - Home" if sys.platform == "darwin" else None)
    im.crop((0, band + 32, 800, 600)).save(path)  # content at the top edge: no strip
    assert images.label_strip(path, 0, "image/png", *images.capture(path, 0, "image/png"), 2) is None
    # Unknown pixel ratio: a strip 35 CSS px tall shot at 2x (70 px) is still a strip, though taller than a 1x strip can be.
    im = Image.new("RGB", (800, 600), "#1f0f3f")
    ImageDraw.Draw(im).rectangle((0, 0, 800, 70), fill="white")
    ImageDraw.Draw(im).text((400, 35), "0.0 Home", fill="#333333", font=ImageFont.load_default(40), anchor="mm")
    im.save(path)
    assert (abs(images.label_strip(path, 0, "image/png", px, box, None)[0] - 70) <= 1, images.label_strip(path, 0, "image/png", px, box, 1)) == (True, None)
    # pages still reports that strip in labelStrip for a 1200 px capture (no known screen): colours and image px, no CSS height.
    im = Image.new("RGB", (1200, 800), "#1f0f3f")
    ImageDraw.Draw(im).rectangle((0, 0, 1200, band), fill="white")
    ImageDraw.Draw(im).text((600, 24), "0.0 Home", fill="#333333", font=font, anchor="mm")
    files.CACHE = Path(d)
    files.urllib.request.urlretrieve = lambda url, dest: im.save(dest, "PNG")  # the "download" of the proof's file
    api.open_proof = lambda url, version=None: ("T", None, None, {"proof": {"name": "P", "version": 1, "versions": 1, "pages": 1, "sourceFiles": [
        {"name": "w.png", "mime": "image/png", "pagesFrom": 1, "pagesTo": 1, "url": "unused"}]}}, [])
    ls = pages.run("unused")["labelStrip"]
    assert (ls["height"], ls["bg"], ls["fg"], abs(ls["heightPx"] - band) <= 1) == (None, "white", "dark grey", True), ls
# screen(): only real (CSS width, ratio) pairs; a width that matches none within 1% is unknown, not the nearest screen.
scr = [images.screen([w, 1000]) for w in (2560, 1024, 2048, 640, 3024, 2388, 1200)]
assert [s["css"] and (s["css"][0], s["dpr"], s["device"]) for s in scr] == [
    (1280, 2, "desktop"), (1024, 1, "desktop"), (1024, 2, "desktop"), (320, 2, "mobile"), (1512, 2, "desktop"), (1194, 2, "desktop"), None], scr
assert [images.colour_name(c) for c in ((255, 255, 255), (51, 51, 51), (31, 15, 63), (249, 173, 66))] == ["white", "dark grey", "dark purple", "orange"]
print("ok")
