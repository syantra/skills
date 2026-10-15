"""pages: every page of the proof in order, as readable image slices, with bookmarks, comments, capture geometry and the label above each capture."""
import functools
from collections import Counter

from wfproof import api, files, images


def register(sub):
    a = sub.add_parser("pages", help="every page in order with image slices, thumbnail, capture size, label, bookmarks and comments")
    a.add_argument("url")
    a.add_argument("--version", type=int, help="read this version instead of the one the link opens")
    a.set_defaults(handler=lambda args: run(args.url, args.version))


def run(url, version=None):
    token, _, _, start, comments = api.open_proof(url, version=version)
    p = start["proof"]
    marks, pages, srcs, boxes, strips = {}, [], [], [], []
    for n in range(1, p["pages"] + 1):
        path, index, mime = files.source_file(token, start, n)
        srcs.append((path, index, mime))
        if path not in marks:
            marks[path] = files.bookmarks(path, mime)
        on_page = sorted((c for c in comments if n in (c.get("pages") or [c["page"]])), key=lambda c: c["number"])
        slices, thumb = images.page_slices(path, index, mime, files.CACHE / token / f"page-{n}")
        px, box = images.capture(path, index, mime)
        scr = images.screen(px)
        strip = px and images.label_strip(path, index, mime, px, box, scr["dpr"])  # dpr None when the width matches no known screen
        boxes.append(box)
        strips.append(strip)
        if strip and scr["css"]:
            scr["css"][1] = round((px[1] - strip[0]) / scr["dpr"])  # the capture is what sits below the strip
        pages.append({
            "page": n,
            "bookmark": marks[path].get(index),
            "label": strip and images.ocr(strip[3]),  # the text of the strip above the capture, as written; not every capture has one
            "comments": [c["number"] for c in on_page],
            "open": sum(not c["isResolved"] for c in on_page),
            **scr,
            "extent": None,  # set below, once the tallest capture per device is known
            "changedFrom": None,
            "images": slices,
            "thumb": thumb,
        })
    # labelStrip: the band most labelled captures share: height in CSS px (null when the pixel ratio is unknown), colours by name,
    # and its usual height in image px.
    band = lambda s, pg: (pg["dpr"] and round(s[0] / pg["dpr"]), images.colour_name(s[1]), images.colour_name(s[2]))
    found = Counter(band(s, pg) for s, pg in zip(strips, pages) if s).most_common(1)
    strip_px = found and Counter(s[0] for s, pg in zip(strips, pages) if s and band(s, pg) == found[0][0]).most_common(1)[0][0]
    # `viewport` (screen only) if under a third of the tallest capture on that device, or no taller than a viewport; else `full`.
    tallest = {}
    for pg in pages:
        if pg["css"]:
            tallest[pg["device"]] = max(tallest.get(pg["device"], 0), pg["css"][1])
    for pg in (pg for pg in pages if pg["css"]):
        (w, h), viewport = pg["css"], 0.75 if pg["device"] == "desktop" else 2.3
        pg["extent"] = "viewport" if h < tallest[pg["device"]] / 3 or h <= viewport * w else "full"

    @functools.cache
    def small(i):  # the capture on page i, below its label strip, drawn 200 px wide in grey
        x0, y0, x1, y1 = boxes[i]
        y0 += strips[i][0] * (x1 - x0) / pages[i]["px"][0] if strips[i] else 0
        return images.render(*srcs[i], *images.page_size(*srcs[i]), (x0, y0, x1, y1), [], 200 / (x1 - x0)).convert("L")

    # changedFrom: what differs from the page before, when both have the same CSS width. Box in CSS px, below the label strip.
    for i in range(1, len(pages)):
        a, b = pages[i - 1], pages[i]
        if a["css"] and b["css"] and a["css"][0] == b["css"][0]:
            box = images.changed_box(small(i - 1), small(i))
            b["changedFrom"] = {"page": a["page"], "box": box and [round(v * b["css"][0] / 200) for v in box]}
    return {
        "proof": p["name"],
        "version": p["version"],
        "latestVersion": p["versions"],
        "sourceFiles": [{"name": f["name"], "pages": [f["pagesFrom"], f["pagesTo"]], "path": str(files.source_file(token, start, f["pagesFrom"])[0])} for f in p["sourceFiles"]],
        "labelStrip": dict(zip(("height", "bg", "fg", "heightPx"), (*found[0][0], strip_px))) if found else None,
        "pages": pages,
    }
