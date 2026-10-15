"""Markup geometry and rendering: boxes in page pixels, crops, page slices, text under a box, the label strip above a screenshot."""
import colorsys
import io
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageDraw

Image.MAX_IMAGE_PIXELS = None  # a full-page screenshot is legitimately huge
MAX_PX = 1600  # longest side of saved images; vision models downscale beyond this anyway
LINES = ("LINE", "ARROW")  # drawn from a start point to an end point; every other markup is a box
SLICE_W = 1150  # page slices are at most this wide so body text stays readable
STRIP_PX = 400  # a label strip is looked for in the top this many image px of a screenshot
# Screens as (CSS width, pixel ratio), to guess how a capture was taken; the first listed wins an exact tie.
# Phones at their own ratio (3) and the ones capture tools emulate them at (1, 2, and 1.5 on a Windows laptop at 150%);
# 1x monitors; tablets, Retina laptops and 4K screens at 2. No 2560@1: a 2560 px capture is 1280@2 far more often.
SCREENS = ([(w, r) for r in (1, 2, 3, 1.5) for w in (320, 360, 375, 390, 393, 412, 414, 428, 430)]
           + [(w, 1) for w in (1024, 1280, 1366, 1440, 1536, 1600, 1680, 1920)]
           + [(w, 2) for w in (834, 1024, 1194, 1280, 1366, 1440, 1512, 1728, 1920)])


def markups(c):
    """Comment -> (page width px, page height px, [(type, x0, y0, x1, y1)]) in source-page pixels.

    Drawing points are relative to the page centre, scaled down by PHQSCALE, y pointing down.
    A box markup gives its corners; a LINE or ARROW its start and end, in that order, so it is drawn
    as the reviewer drew it (an arrow's tip is its end). bbox() gives the area they cover.
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
        if d["type"] in LINES:
            out.append((d["type"], xs[0], ys[0], xs[-1], ys[-1]))
        else:
            out.append((d["type"], min(xs), min(ys), max(xs), max(ys)))
    if not out and c.get("pinPoint"):
        x, y = c["pinPoint"]["x"] * S + W / 2, c["pinPoint"]["y"] * S + H / 2
        out.append(("PIN", x, y, x, y))
    return W, H, out


def bbox(boxes):
    """The area the markups cover, (x0, y0, x1, y1); a line's end can sit left of or above its start."""
    return (min(min(b[1], b[3]) for b in boxes), min(min(b[2], b[4]) for b in boxes),
            max(max(b[1], b[3]) for b in boxes), max(max(b[2], b[4]) for b in boxes))


def render(path, index, mime, W, H, region, boxes, scale=None):
    """Render a region (source-page px) of the page, with the markups in red: boxes outlined, lines and arrows along their path."""
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
        mode = "RGBA" if src.has_transparency_data else "RGB"  # a CMYK or grey source still saves as PNG and takes red marks
        img = src.crop((x0 * k, y0 * k, x1 * k, y1 * k)).convert(mode).resize((max(1, round((x1 - x0) * scale)), max(1, round((y1 - y0) * scale))))
    draw = ImageDraw.Draw(img)
    for t, bx0, by0, bx1, by1 in boxes:
        (ax, ay), (bx, by) = ((bx0 - x0) * scale, (by0 - y0) * scale), ((bx1 - x0) * scale, (by1 - y0) * scale)
        if t in LINES:  # a strikethrough, a slash or an arrow, along its path; a dot marks an arrow's tip
            draw.line([(ax, ay), (bx, by)], fill="red", width=4)
            if t == "ARROW":
                draw.ellipse([bx - 7, by - 7, bx + 7, by + 7], fill="red")
        else:
            r = 6 if t == "PIN" else 0  # pins are points; draw a small ring
            draw.rectangle([ax - r, ay - r, bx + r, by + r], outline="red", width=3)
    return img


def text_in_box(path, index, mime, W, boxes):
    """Exact text under the markup when the source is a PDF with a text layer, else None:
    what a box covers, what a line crosses, the words at an arrow's tip (not everything the arrow spans)."""
    if mime != "application/pdf":
        return None
    page = pdfium.PdfDocument(path)[index]
    w, h = page.get_size()
    k = W / w
    tp = page.get_textpage()
    text = []
    for t, ax, ay, bx, by in boxes:
        if t == "ARROW":  # its start can sit on unrelated text
            ax, ay = bx, by
        dx, dy = {"ARROW": (24, 6), "LINE": (2, 2)}.get(t, (0, 0))  # PDF points around a tip or a thin line, so it meets the text
        left, right = min(ax, bx) / k - dx, max(ax, bx) / k + dx
        if right > left:  # not a pin
            text.append(tp.get_text_bounded(left=left, bottom=h - max(ay, by) / k - dy, right=right, top=h - min(ay, by) / k + dy))
    return " ".join(text).strip() or None


def capture(path, index, mime):
    """The screenshot on a page -> (its pixel size, its box in page units, y down): the image itself, or a PDF page's largest image
    if it covers >= 90% of the page; (None, None) otherwise."""
    if mime != "application/pdf":
        w, h = Image.open(path).size
        return [w, h], (0, 0, w, h)
    page = pdfium.PdfDocument(path)[index]
    w, h = page.get_size()
    best, px, box = 0, None, None
    for o in page.get_objects([pdfium.raw.FPDF_PAGEOBJ_IMAGE]):
        l, b, r, t = o.get_bounds()
        if (r - l) * (t - b) > best:
            best, px, box = (r - l) * (t - b), list(o.get_px_size()), (l, h - t, r, h - b)
    return (px, box) if best >= 0.9 * w * h else (None, None)


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


def colour_name(rgb):
    """Coarse name: white, black, light/dark grey, or a hue (red, orange, yellow, green, cyan, blue, purple, pink), light/dark when it is."""
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in rgb))
    if s < 0.15 or l > 0.95 or l < 0.08:
        return "white" if l > 0.9 else "black" if l < 0.12 else "light grey" if l > 0.5 else "dark grey"
    hue = next(n for stop, n in ((15, "red"), (45, "orange"), (70, "yellow"), (160, "green"), (200, "cyan"), (260, "blue"), (300, "purple"), (345, "pink"), (361, "red")) if h * 360 < stop)
    return ("light " if l > 0.65 else "dark " if l < 0.3 else "") + hue


def label_strip(path, index, mime, px, box, dpr):
    """The label a capture tool printed above a screenshot: a band of one colour at the top of the image holding one line of text, whatever it says.

    `px` and `box` come from capture(); `dpr` is None when unknown, and a strip shot at 2x still fits. -> (strip height in image px, bg rgb, fg rgb, image of the text line), or None when the image does not start with such a band.
    """
    limit, dpr = 60 * (dpr or 2), dpr or 1
    x0, y0, x1, y1 = box
    k = px[0] / (x1 - x0)  # image px per page unit
    top = render(path, index, mime, *page_size(path, index, mime), (x0, y0, x1, min(y1, y0 + STRIP_PX / k)), [], k).convert("RGB")
    w, h = top.size
    bg = top.getpixel((0, 0))
    mask = ImageChops.difference(top, Image.new("RGB", top.size, bg)).convert("L").point(lambda v: 255 if v > 40 else 0)
    rows = mask.reduce((w, 1)).get_flattened_data()  # mean of each row: 0 where the row is all bg

    def run(y, blank):  # first row from y that is not blank (or is, when blank is False)
        while y < h and (rows[y] == 0) == blank:
            y += 1
        return y
    a = run(0, True)  # top padding
    b = run(a, False)  # the text line
    c = run(b, True)  # bottom padding
    while 0 < c - b < 3 * dpr and c < h:  # a descender right under the line: still the text
        b = run(c, False)
        c = run(b, True)
    if a == 0 or c >= h:  # content at the top edge, or nothing but the band in the top STRIP_PX
        return None
    if c > a + b + 4 * dpr:  # the band runs well past where a centred text line says it ends: the page's own blank top, in the same colour
        c = a + b
    if c > limit:  # taller than a label strip: a page header
        return None
    tx0, _, tx1, _ = mask.crop((0, a, w, b)).getbbox()
    text = top.crop((max(0, tx0 - 40), 0, min(w, tx1 + 40), c))
    fg = max(text.get_flattened_data(), key=lambda p: sum(abs(p[i] - bg[i]) for i in range(3)))
    return c, bg, fg, text


def ocr(img):
    """Text in a PIL image, read by macOS's Vision framework; None on other platforms (pyobjc is installed on macOS only) or when it reads nothing."""
    try:
        import Vision
        from Foundation import NSData
    except ImportError:
        return None
    buf = io.BytesIO()
    img.save(buf, "PNG")
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    data = NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
    Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None).performRequests_error_([req], None)
    return " ".join(o.topCandidates_(1)[0].string() for o in req.results() or []) or None


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
    px = capture(path, index, mime)[0]
    # One scale per page: the whole page in one image if that is at least slice-width sharp, else SLICE_W-wide slices;
    # up to the screenshot's own pixels when a PDF page holds more of them than it has points.
    scale = min(max(1, px[0] / W) if px else 1, MAX_PX / W, max(SLICE_W / W, MAX_PX / H))
    out_prefix = f"{out_prefix}-{round(W * scale)}w"  # slices cached at another scale are not reused
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
