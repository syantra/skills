# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdfium2==5.14.0", "pillow==12.3.0"]
# ///
"""Offline check for wfproof.images: markup -> pixel math, rendering sizes.

Run: uv run tests/test_images.py
"""
import sys
import tempfile
from pathlib import Path

import pypdfium2 as pdfium

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "workfront-proof" / "scripts"))
from wfproof import images

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

# Render a region of a 100x200pt PDF page shown in the viewer as 400x800px.
with tempfile.TemporaryDirectory() as d:
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(100, 200)
    path = Path(d) / "p.pdf"
    pdf.save(path)
    assert images.render(path, 0, "application/pdf", 400, 800, (100, 200, 300, 600), [("RECTANGLE", 150, 250, 250, 550)]).size == (200, 400)
    assert images.render(path, 0, "application/pdf", 400, 800, (0, 0, 400, 3200), []).size == (200, 1600)  # capped at MAX_PX
print("ok")
