"""show: one comment in full, with crop and context images of what the reviewer marked."""
import pypdfium2 as pdfium
from PIL import UnidentifiedImageError

from wfproof import api, files, images
from wfproof.text import plain, when


def register(sub):
    a = sub.add_parser("show", help="one comment with markup boxes, crop and context images")
    a.add_argument("url")
    a.add_argument("number", nargs="?", type=int)
    a.add_argument("--version", type=int, help="read this version instead of the one the link opens")
    a.set_defaults(handler=lambda args: run(args.url, args.number, args.version))


def run(url, number, version=None):
    token, from_url, _, start, comments = api.open_proof(url, version=version)
    number = number or from_url
    if number is None:
        raise SystemExit("Give a comment number, or use a URL ending in #comment:N.")
    c = api.find_comment(comments, number)
    W, H, boxes = images.markups(c)
    path, index, mime = files.source_file(token, start, c["page"])
    out = files.CACHE / token
    result = {
        "proof": start["proof"]["name"],
        "version": start["proof"]["version"],
        "number": c["number"],
        "page": c["page"],
        "pages": c.get("pages") or [c["page"]],
        "author": c["author"],
        "created": when(c["created"]),
        "text": plain(c["text"]),
        "action": c.get("actionName"),
        "resolved": c["isResolved"],
        "attachments": c.get("attachments") or [],  # as the API sends them
        "replies": [
            {"id": r.get("id"), "number": f'{c["number"]}.{r.get("number")}', "author": r.get("author"), "created": when(r.get("created")),
             "text": plain(r.get("text")), "action": r.get("actionName"), "attachments": r.get("attachments") or []}
            for r in c.get("replies") or []
        ],
        "pageSize": [W, H],
        "markups": [{"type": t, "line" if t in images.LINES else "box": [round(v) for v in b]} for t, *b in boxes],
        "sourceFile": path.name,
    }
    try:
        images.page_size(path, index, mime)  # opens the source: a DOCX or other non-image fails here, with or without markup on this comment
        if boxes:
            x0, y0, x1, y1 = images.bbox(boxes)
            pad = max(250, 0.5 * max(x1 - x0, y1 - y0))
            crop = images.render(path, index, mime, W, H, images.clip((x0 - pad, y0 - pad, x1 + pad, y1 + pad), W, H), boxes)
            cy = (y0 + y1) / 2
            context = images.render(path, index, mime, W, H, images.clip((0, cy - 0.75 * W, W, cy + 0.75 * W), W, H), boxes)
            result["textInBox"] = images.text_in_box(path, index, mime, W, boxes)
            result["crop"] = str(out / f"comment-{number}-crop.png")
            result["context"] = str(out / f"comment-{number}-context.png")
            crop.save(result["crop"])
            context.save(result["context"])
    except (UnidentifiedImageError, pdfium.PdfiumError):
        result["note"] = f"Source type {mime} is not rendered (only PDF and image sources are), so there is no crop or context image; `markups` still gives the marked area."
    return result
