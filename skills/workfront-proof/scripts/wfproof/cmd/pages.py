"""pages: every page of the proof in order, as readable image slices, with bookmarks, comments and capture geometry."""
import functools

from wfproof import api, files, images


def register(sub):
    a = sub.add_parser("pages", help="every page in order with image slices, thumbnail, capture size, bookmarks and comments")
    a.add_argument("url")
    a.add_argument("--version", type=int, help="read this version instead of the one the link opens")
    a.set_defaults(handler=lambda args: run(args.url, args.version))


def run(url, version=None):
    token, _, _, start, comments = api.open_proof(url, version=version)
    p = start["proof"]
    marks, pages, srcs = {}, [], []
    for n in range(1, p["pages"] + 1):
        path, index, mime = files.source_file(token, start, n)
        srcs.append((path, index, mime))
        if path not in marks:
            marks[path] = files.bookmarks(path, mime)
        on_page = sorted((c for c in comments if n in (c.get("pages") or [c["page"]])), key=lambda c: c["number"])
        slices, thumb = images.page_slices(path, index, mime, files.CACHE / token / f"page-{n}")
        pages.append({
            "page": n,
            "bookmark": marks[path].get(index),
            "comments": [c["number"] for c in on_page],
            "open": sum(not c["isResolved"] for c in on_page),
            **images.screen(images.capture_px(path, index, mime)),
            "extent": None,  # set below, once the tallest capture per device is known
            "changedFrom": None,
            "images": slices,
            "thumb": thumb,
        })
    # `viewport` (screen only) if under a third of the tallest capture on that device, or no taller than a viewport; else `full`.
    tallest = {}
    for pg in pages:
        if pg["css"]:
            tallest[pg["device"]] = max(tallest.get(pg["device"], 0), pg["css"][1])
    for pg in (pg for pg in pages if pg["css"]):
        (w, h), viewport = pg["css"], 0.75 if pg["device"] == "desktop" else 2.3
        pg["extent"] = "viewport" if h < tallest[pg["device"]] / 3 or h <= viewport * w else "full"

    @functools.cache
    def small(i):  # page i drawn 200 px wide in grey
        W, H = images.page_size(*srcs[i])
        return images.render(*srcs[i], W, H, (0, 0, W, H), [], 200 / W).convert("L")

    # changedFrom: what differs from the page before, when both have the same CSS width. Box in CSS px.
    for i in range(1, len(pages)):
        a, b = pages[i - 1], pages[i]
        if a["css"] and b["css"] and a["css"][0] == b["css"][0]:
            box = images.changed_box(small(i - 1), small(i))
            b["changedFrom"] = {"page": a["page"], "box": box and [round(v * b["css"][0] / 200) for v in box]}
    return {
        "proof": p["name"],
        "version": p["version"],
        "latestVersion": p["versions"],
        "sourceFiles": [{"name": f["name"], "pages": [f["pagesFrom"], f["pagesTo"]], "path": str(files.CACHE / token / f["name"])} for f in p["sourceFiles"]],
        "pages": pages,
    }
