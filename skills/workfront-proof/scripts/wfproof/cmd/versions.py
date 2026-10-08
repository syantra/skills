"""versions: every version of the proof, oldest first, and which one the link opens."""
from wfproof import api
from wfproof.text import when


def register(sub):
    a = sub.add_parser("versions", help="every version with date, file type, comment and reply counts")
    a.add_argument("url")
    a.set_defaults(handler=lambda args: run(args.url))


def run(url):
    _, _, tenant, start = api.session(url)
    items = api.rpc(tenant, "versions", sessionId=start["sessionId"], only_processed=False)["items"]
    return {
        "proof": start["proof"]["name"],
        "linkOpens": start["proof"]["version"],
        "latest": start["proof"]["versions"],
        "versions": [
            {
                "version": v["version"],
                "created": when(v["created"]),
                "file": v["mime"],
                "comments": v["commentsCount"],
                "replies": v["repliesCount"],
                "processed": v["isProcessed"],
            }
            for v in sorted(items, key=lambda v: v["version"])
        ],
    }
