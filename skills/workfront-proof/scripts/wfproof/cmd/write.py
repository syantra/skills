"""reply, resolve, delete-reply: changes to the proof, run as the signed-in reviewer.

All three preview by default and only act with --send, so they share one flow: check identity
and permission, preview or perform, then re-read the comment to confirm.
"""
from wfproof import api
from wfproof.text import plain


def register(sub):
    a = sub.add_parser("reply", help="reply to a comment (preview unless --send)")
    a.add_argument("url")
    a.add_argument("number", type=int)
    a.add_argument("text")
    a.add_argument("--send", action="store_true")
    a.set_defaults(handler=lambda args: run(args.url, args.number, "reply", args.text, args.send))
    a = sub.add_parser("resolve", help="resolve a comment, or reopen it with --reopen (preview unless --send)")
    a.add_argument("url")
    a.add_argument("number", type=int)
    a.add_argument("--reopen", action="store_true")
    a.add_argument("--send", action="store_true")
    a.set_defaults(handler=lambda args: run(args.url, args.number, "reopen" if args.reopen else "resolve", None, args.send))
    a = sub.add_parser("delete-reply", help="delete one reply on a comment (preview unless --send)")
    a.add_argument("url")
    a.add_argument("number", type=int)
    a.add_argument("reply_id", type=int)
    a.add_argument("--send", action="store_true")
    a.set_defaults(handler=lambda args: run(args.url, args.number, "delete-reply", None, args.send, args.reply_id))


def run(url, number, action, text=None, send=False, reply_id=None):
    """Preview a reply / resolve / reopen / delete-reply on one comment; with send=True, perform it as the signed-in reviewer."""
    _, _, tenant, start, comments = api.open_proof(url, identify=True)
    c = api.find_comment(comments, number)
    me = (start.get("recipient") or {}).get("name")
    replies = c.get("replies") or []
    result = {"action": action, "number": c["number"], "comment": plain(c["text"]), "resolved": c["isResolved"], "as": me}
    if action == "delete-reply":
        r = next((r for r in replies if r["id"] == reply_id), None)
        if r is None:
            raise SystemExit(f"Comment {number} has no reply {reply_id}. Its reply ids: {[x['id'] for x in replies]}.")
        result["reply"] = {"id": r["id"], "author": r.get("author"), "text": r.get("text")}
        allowed, why = bool(r["permissions"] & api.CAN_DELETE), f"Your role doesn't allow deleting reply {reply_id}."
    else:
        # ponytail: replies are left for Workfront to judge at send time; it answers with a readable error.
        allowed = action == "reply" or bool(c["permissions"] & api.CAN_RESOLVE)
        why = f"Your role on this proof doesn't allow resolving comment {number}. Leave it for the proof owner or the comment's author."
    result["allowed"] = allowed
    if text is not None:
        result["text"] = text
    refusal = None if me and allowed else 'Not signed in: run `uv run scripts/login.py "<review-url>"` first.' if not me else why
    if not send:
        result["sent"] = False
        result["next"] = refusal or "Show this to the user. Rerun with --send only after they approve this exact action."
        return result
    if refusal:
        raise SystemExit(refusal)
    sid = start["sessionId"]
    if action == "reply":
        api.rpc(tenant, "add_reply", sessionId=sid, commentId=c["id"], text=text, notifyRecipients=[], attachmentIds=[])
    elif action == "delete-reply":
        api.rpc(tenant, "delete_reply", sessionId=sid, replyId=reply_id)
    else:
        api.rpc(tenant, "resolve_comment" if action == "resolve" else "unresolve_comment", sessionId=sid, commentId=c["id"])
    after = api.find_comment(api.rpc(tenant, "comments", sessionId=sid)["items"], number)
    result.update(sent=True, resolvedAfter=after["isResolved"], repliesAfter=len(after.get("replies") or []))
    new = [r for r in after.get("replies") or [] if r["id"] not in {x["id"] for x in replies}]
    if new:
        result["newReply"] = {"id": new[0]["id"], "author": new[0].get("author"), "text": new[0].get("text")}
    return result
