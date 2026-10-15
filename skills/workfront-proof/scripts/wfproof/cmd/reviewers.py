"""reviewers: the review stages, and each reviewer's role and decision."""
from wfproof import api
from wfproof.text import label, when


def register(sub):
    a = sub.add_parser("reviewers", help="review stages with each reviewer's role and decision")
    a.add_argument("url")
    a.add_argument("--version", type=int, help="read this version instead of the one the link opens")
    a.set_defaults(handler=lambda args: run(args.url, args.version))


def decision(d):
    return label((d or {}).get("name"), "decision")


def run(url, version=None):
    _, _, tenant, start = api.session(url, version=version)
    stages = api.rpc(tenant, "recipients", sessionId=start["sessionId"])["items"]
    return {
        "proof": start["proof"]["name"],
        "version": start["proof"]["version"],
        "latestVersion": start["proof"]["versions"],
        "decision": decision(start["proof"].get("decision")),  # overall outcome
        "stages": [
            {
                "stage": s["name"],
                "active": s["isActive"],
                "deadline": when(s.get("deadline")),
                "decision": decision(s.get("decision")),  # stage outcome; None until an approver decides
                "reviewers": [
                    {
                        "name": r["name"],
                        "role": label(r.get("roleName"), "role"),
                        "decision": decision(r.get("decision")),  # "Not relevant" with no date: they didn't need to decide
                        "decidedAt": when(r.get("decisionAt")),
                        "primaryDecisionMaker": r.get("isPrimaryDecisionMaker"),
                        "comments": r.get("commentsCount"),
                    }
                    for r in s.get("items") or []
                ],
            }
            for s in stages
        ],
    }
