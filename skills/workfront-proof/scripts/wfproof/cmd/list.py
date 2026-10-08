"""list: a proof's comments, open ones only unless --all."""
from wfproof import api
from wfproof.text import plain


def register(sub):
    a = sub.add_parser("list", help="open comments (all with --all)")
    a.add_argument("url")
    a.add_argument("--all", action="store_true")
    a.add_argument("--version", type=int, help="read this version instead of the one the link opens")
    a.set_defaults(handler=lambda args: run(args.url, args.all, args.version))


def run(url, show_all, version=None):
    _, _, _, start, comments = api.open_proof(url, version=version)
    p = start["proof"]
    rows = [
        {
            "number": c["number"],
            "page": c["page"],
            "pages": c.get("pages") or [c["page"]],
            "author": c["author"],
            "text": plain(c["text"]),
            "action": c.get("actionName"),
            "resolved": c["isResolved"],
            "replies": len(c.get("replies") or []),
            "markup": [d["type"] for d in c.get("drawings") or []] or (["PIN"] if c.get("pinPoint") else []),
        }
        for c in sorted(comments, key=lambda c: c["number"])
        if show_all or not c["isResolved"]
    ]
    return {
        "proof": p["name"],
        "version": p["version"],
        "latestVersion": p["versions"],
        "pages": p["pages"],
        "identifiedAs": (start.get("recipient") or {}).get("name"),  # None = anonymous link session
        "open": sum(not c["isResolved"] for c in comments),
        "total": len(comments),
        "comments": rows,
    }
