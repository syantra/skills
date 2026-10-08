"""Markup geometry and rendering: boxes in page pixels, crops, page slices, text under a box."""
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageDraw

MAX_PX = 1600  # longest side of saved images; vision models downscale beyond this anyway
SLICE_W = 1150  # page slices are at most this wide so body text stays readable
# Common screens as (CSS width, pixel ratio), to guess how a capture was taken. Integer ratios come first and win exact ties.
SCREENS = ([(w, r) for r in (1, 2, 3, 1.5, 2.625) for w in (360, 375, 390, 393, 412, 414, 428, 430)]
           + [(w, r) for r in (1, 2, 1.5, 1.25) for w in (1280, 1366, 1440, 1536, 1600, 1680, 1728, 1920, 2560)])


def markups(c):
    """Comment -> (page width px, page height px, [(type, x0, y0, x1, y1)]) in source-page pixels.

    Drawing points are relative to the page centre, scaled down by PHQSCALE, y pointing down.
    Comments without drawings fall back to their pin as a zero-size box.
    A comment can span pages (`pages`); only drawings on its first page are returned.
    """
    size = c["metadata"]["pageSizes"][str(c["page"])]
    W, H, S = size["WIDTH"], size["HEIGHT"], size["PHQSCALE"]
    out = []
    # ponytail: crop covers the first page only; render per page if reviewers mark different things across pages
    for d in (d for d in c.get("drawings") or [] if d.get("page", c["page"]) == c["page"]):
        xs = [p["x"] * S + W / 2 for p in d["points"]]
        ys = [p["y"] * S + H / 2 for p in d["points"]]
        out.append((d["type"], min(xs), min(ys), max(xs), max(ys)))
    if not out and c.get("pinPoint"):
        x, y = c["pinPoint"]["x"] * S + W / 2, c["pinPoint"]["y"] * S + H / 2
        out.append(("PIN", x, y, x, y))
    return W, H, out


def render(path, index, mime, W, H, region, boxes, scale=None):
    """Render a region (source-page px) of the page, with the marked boxes outlined in red."""
    x0, y0, x1, y1 = region
    scale = scale or min(1, MAX_PX / max(x1 - x0, y1 - y0, 1))
    if mime == "application/pdf":
        page = pdfium.PdfDocument(path)[index]
        w, h = page.get_size()
        k = W / w  # source px per PDF point
        img = page.render(scale=k * scale, crop=(x0 / k, h - y1 / k, w - x1 / k, y0 / k)).to_pil()
    else:  # image proofs: ponytail: one image per file assumed, check multi-frame files when we meet one
        src = Image.open(path)
        k = src.width / W
        img = src.crop((x0 * k, y0 * k, x1 * k, y1 * k)).resize((max(1, round((x1 - x0) * scale)), max(1, round((y1 - y0) * scale))))
    draw = ImageDraw.Draw(img)
    for _, bx0, by0, bx1, by1 in boxes:
        r = 6 if bx0 == bx1 else 0  # pins are points; draw a small ring
        draw.rectangle([(bx0 - x0) * scale - r, (by0 - y0) * scale - r, (bx1 - x0) * scale + r, (by1 - y0) * scale + r], outline="red", width=3)
    return img


def text_in_box(path, index, mime, W, boxes):
    """Exact text under the markup when the source is a PDF with a text layer, else None."""
    if mime != "application/pdf":
        return None
    page = pdfium.PdfDocument(path)[index]
    w, h = page.get_size()
    k = W / w
    tp = page.get_textpage()
    text = " ".join(tp.get_text_bounded(left=bx0 / k, bottom=h - by1 / k, right=bx1 / k, top=h - by0 / k) for _, bx0, by0, bx1, by1 in boxes if bx1 > bx0)
    return text.strip() or None


def capture_px(path, index, mime):
    """Pixel size of the screenshot: the image itself, or a PDF page's largest image if it covers >= 90% of the page, else None."""
    if mime != "application/pdf":
        return list(Image.open(path).size)
    page = pdfium.PdfDocument(path)[index]
    w, h = page.get_size()
    best, px = 0, None
    for o in page.get_objects([pdfium.raw.FPDF_PAGEOBJ_IMAGE]):
        l, b, r, t = o.get_bounds()
        if (r - l) * (t - b) > best:
            best, px = (r - l) * (t - b), list(o.get_px_size())
    return px if best >= 0.9 * w * h else None


def screen(px):
    """Guess how a capture was taken: the common screen whose width is closest to the capture's, within 1%. Fields are None if none is."""
    out = {"px": px, "css": None, "dpr": None, "device": None}
    if px:
        w, r = min(SCREENS, key=lambda s: abs(px[0] / (s[0] * s[1]) - 1))
        if abs(px[0] / (w * r) - 1) <= 0.01:
            out.update(css=[w, round(px[1] / r)], dpr=r, device="mobile" if w < 768 else "desktop")
    return out


def changed_box(a, b):
    """Where grey image b differs from a, as (x0, y0, x1, y1) in b's pixels; None if they match.

    The change starts where they first differ aligned at the top, and ends where they last differ aligned at the
    bottom (or at the top, if sooner), so content that only moved below the change does not count.
    """
    def diff(dy):  # differing pixels, with a shifted down by dy onto b's canvas
        shifted = Image.new("L", b.size)
        shifted.paste(a, (0, dy))
        return ImageChops.difference(shifted, b).point(lambda v: 255 if v > 40 else 0)
    top = diff(0)
    box, bottom = top.getbbox(), diff(b.height - a.height).getbbox()
    if not box:
        return None
    y0, y1 = box[1], max(box[1] + 1, min(box[3], bottom[3]) if bottom else box[3])
    x0, _, x1, _ = top.crop((0, y0, b.width, y1)).getbbox()
    return x0, y0, x1, y1


def page_size(path, index, mime):
    """Page size: PDF points, or pixels for image proofs."""
    if mime == "application/pdf":
        return pdfium.PdfDocument(path)[index].get_size()
    return Image.open(path).size


def clip(region, W, H):
    x0, y0, x1, y1 = region
    return max(0, x0), max(0, y0), min(W, x1), min(H, y1)


def page_slices(path, index, mime, out_prefix):
    """Cut one page top-to-bottom into readable images (<= MAX_PX tall, <= SLICE_W wide), plus a whole-page thumbnail. Cached."""
    W, H = page_size(path, index, mime)
    # One scale per page: the whole page in one image if that is at least slice-width sharp, else SLICE_W-wide slices.
    scale = min(1, MAX_PX / W, max(SLICE_W / W, MAX_PX / H))
    step = MAX_PX / scale  # source height of one slice
    paths, y = [], 0
    while y < H:
        out = Path(f"{out_prefix}-{len(paths) + 1}.png")
        if not out.exists():
            render(path, index, mime, W, H, (0, y, W, min(H, y + step)), [], scale).save(out)
        paths.append(str(out))
        y += step
    thumb = Path(f"{out_prefix}-thumb.png")
    if len(paths) == 1:
        return paths, paths[0]
    if not thumb.exists():  # the slices side by side, shrunk to fit MAX_PX
        tiles = [Image.open(p) for p in paths]
        sheet = Image.new("RGB", (tiles[0].width * len(tiles), tiles[0].height), "white")
        for i, t in enumerate(tiles):
            sheet.paste(t, (i * tiles[0].width, 0))
        sheet.thumbnail((MAX_PX, MAX_PX))
        sheet.save(thumb)
    return paths, str(thumb)
