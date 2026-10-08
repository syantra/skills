# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdfium2==5.14.0", "pillow==12.3.0"]
# ///
"""Offline check for wfproof.cmd.*: list filtering, write gating, pages slicing. Uses a fake RPC.

Run: uv run tests/test_commands.py
"""
import importlib
import sys
import tempfile
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "workfront-proof" / "scripts"))
from wfproof import api, files

list_cmd = importlib.import_module("wfproof.cmd.list")
pages_cmd = importlib.import_module("wfproof.cmd.pages")
reviewers_cmd = importlib.import_module("wfproof.cmd.reviewers")
versions_cmd = importlib.import_module("wfproof.cmd.versions")
write_cmd = importlib.import_module("wfproof.cmd.write")

URL = ("https://example.my.workfront.adobe.com/proof/review/0123456789abcdef0123456789abcdef-PROOFTOKEN0000000000000000000000-t0000000"
       "?tcmsTenantId=00000000000000000000000000000000")
SIGNED = URL + "#proof:CODE123,token:PROOFTOKEN0000000000000000000000"

# list hides resolved comments unless --all.
calls = []
STATE = {"resolved": False, "replies": [{"id": 70, "author": "Sam", "text": "theirs", "permissions": 32}]}


def fake_rpc(tenant, method, **kw):
    calls.append((method, kw))
    if method == "startup":
        me = {"name": "Me"} if kw["proofingCode"] == "CODE123" else None
        return {"sessionId": "s", "recipient": me, "proof": {"name": "P", "version": 2, "versions": 2, "pages": 1}}
    if method == "resolve_comment":
        STATE["resolved"] = True
        return {"responseClass": "commentResponse"}
    if method == "add_reply":
        STATE["replies"].append({"id": 71, "author": "Me", "text": kw["text"], "permissions": 35})
        return {"responseClass": "replyResponse"}
    if method == "delete_reply":
        STATE["replies"] = [r for r in STATE["replies"] if r["id"] != kw["replyId"]]
        return {"responseClass": "successResponse"}
    return {"items": [{"id": 902, "number": 2, "page": 1, "author": "A", "text": "b", "isResolved": True, "drawings": [], "pinPoint": None, "permissions": 32},
                      {"id": 901, "number": 1, "page": 1, "author": "A", "text": "a", "isResolved": STATE["resolved"], "drawings": [{"type": "ARROW"}], "permissions": 48, "replies": list(STATE["replies"]), "actionName": "STET"}]}


api.rpc = fake_rpc
api.CODES = Path(tempfile.mkdtemp()) / "codes.json"  # never touch the real saved codes
out = list_cmd.run(URL, False)
assert [c["number"] for c in out["comments"]] == [1] and out["open"] == 1 and out["identifiedAs"] is None
assert out["comments"][0]["action"] == "STET"
assert [c["number"] for c in list_cmd.run(URL, True)["comments"]] == [1, 2]

# Writes: preview never calls a write method; --send needs a signed-in reviewer and targets the comment id.
pre = write_cmd.run(URL, 1, "resolve")
assert pre["sent"] is False and pre["as"] is None and not any(m.endswith("_comment") or m == "add_reply" for m, _ in calls)
try:
    write_cmd.run(URL, 1, "resolve", send=True)
    raise AssertionError("anonymous send must refuse")
except SystemExit:
    pass
done = write_cmd.run(SIGNED, 1, "resolve", send=True)
assert done["as"] == "Me" and done["sent"] and done["resolvedAfter"] is True
assert ("resolve_comment", {"sessionId": "s", "commentId": 901}) in calls
assert write_cmd.run(SIGNED, 2, "resolve")["allowed"] is False  # permissions 32 lacks CAN_RESOLVE
n = len(calls)
try:
    write_cmd.run(SIGNED, 2, "resolve", send=True)
    raise AssertionError("send without CAN_RESOLVE must refuse")
except SystemExit:
    pass
assert not any(m == "resolve_comment" for m, _ in calls[n:])  # refused locally, nothing sent

# Reply round trip: send reports the new reply id; deleting needs CAN_DELETE on that reply.
posted = write_cmd.run(SIGNED, 1, "reply", "Done!", send=True)
assert posted["newReply"] == {"id": 71, "author": "Me", "text": "Done!"} and posted["repliesAfter"] == 2
assert write_cmd.run(SIGNED, 1, "delete-reply", reply_id=70)["allowed"] is False  # someone else's reply (32)
pre = write_cmd.run(SIGNED, 1, "delete-reply", reply_id=71)
assert pre["allowed"] is True and pre["sent"] is False and pre["reply"]["text"] == "Done!"
gone = write_cmd.run(SIGNED, 1, "delete-reply", send=True, reply_id=71)
assert gone["repliesAfter"] == 1 and ("delete_reply", {"sessionId": "s", "replyId": 71}) in calls

# pages: every page in order, cut into readable slices; comments mapped to their page.
files.CACHE = Path(tempfile.mkdtemp())
src = files.CACHE / "PROOFTOKEN0000000000000000000000" / "p.pdf"
src.parent.mkdir(parents=True)
doc = pdfium.PdfDocument.new()
doc.new_page(2300, 5000)  # wide page: slices are SLICE_W wide, 2 of them
doc.new_page(100, 4000)   # narrow page: kept at its width, 3 slices
doc.save(src)
api.rpc = lambda tenant, method, **kw: (
    {"sessionId": "s", "proof": {"name": "P", "version": 1, "versions": 1, "pages": 2,
                                 "sourceFiles": [{"name": "p.pdf", "mime": "application/pdf", "pagesFrom": 1, "pagesTo": 2, "url": "unused"}]}}
    if method == "startup" else
    {"items": [{"number": 3, "page": 2, "isResolved": False}, {"number": 1, "page": 2, "isResolved": True}, {"number": 9, "page": 1, "pages": [1, 2], "isResolved": False}]})
lay = pages_cmd.run(URL)
sizes = [[Image.open(i).size for i in p["images"]] for p in lay["pages"]]
assert sizes == [[(1150, 1600), (1150, 900)], [(100, 1600), (100, 1600), (100, 800)]], sizes
assert lay["pages"][0]["comments"] == [9] and lay["pages"][1]["comments"] == [1, 3, 9] and lay["pages"][1]["open"] == 2  # 9 spans both pages
assert lay["sourceFiles"][0]["path"] == str(src) and lay["pages"][0]["bookmark"] is None
assert pages_cmd.run(URL)["pages"][1]["images"] == lay["pages"][1]["images"]  # second run reuses cached slices
assert [Image.open(p["thumb"]).size for p in lay["pages"]] == [(1600, 1113), (300, 1600)]  # slices side by side, fit in MAX_PX
assert lay["pages"][0]["css"] is None and lay["pages"][0]["extent"] is None  # no image on the page: no capture geometry

# pages: capture geometry from the page's image (not the PDF page size), extent, and the change from the page before.
files.CACHE = Path(tempfile.mkdtemp())
src = files.CACHE / "PROOFTOKEN0000000000000000000000" / "shots.pdf"
src.parent.mkdir(parents=True)
plain, barred = Image.new("RGB", (1440, 3000), "white"), Image.new("RGB", (1440, 3000), "white")
barred.paste((0, 0, 0), (0, 100, 1440, 200))  # same capture with a black bar at y 100-200
doc = pdfium.PdfDocument.new()
for shot, (w, h) in [(plain, (1440, 3000)), (barred, (1440, 3000)), (Image.new("RGB", (430, 900), "white"), (400, 837))]:
    page = doc.new_page(w, h)
    img = pdfium.PdfImage.new(doc)
    img.set_bitmap(pdfium.PdfBitmap.from_pil(shot))
    img.set_matrix(pdfium.PdfMatrix().scale(w, h))
    page.insert_obj(img)
    page.gen_content()
doc.save(src)
api.rpc = lambda tenant, method, **kw: (
    {"sessionId": "s", "proof": {"name": "P", "version": 1, "versions": 1, "pages": 3,
                                 "sourceFiles": [{"name": "shots.pdf", "mime": "application/pdf", "pagesFrom": 1, "pagesTo": 3, "url": "unused"}]}}
    if method == "startup" else {"items": []})
a, b, c = pages_cmd.run(URL)["pages"]
assert (a["css"], a["dpr"], a["device"], a["extent"], a["changedFrom"]) == ([1440, 3000], 1, "desktop", "full", None), a
box = b["changedFrom"]["box"]
assert b["changedFrom"]["page"] == 1 and abs(box[1] - 100) <= 8 and abs(box[3] - 200) <= 8, b["changedFrom"]
assert (c["px"], c["css"], c["device"], c["extent"], c["changedFrom"]) == ([430, 900], [430, 900], "mobile", "viewport", None), c

# versions, and --version N: switch to that version's own token before reading.
def fake_versions(tenant, method, **kw):
    calls.append((method, kw))
    if method == "startup":
        v = {"TOK1": 1, "PROOFTOKEN0000000000000000000000": 2}[kw["token"]]
        return {"sessionId": f"s{v}", "recipient": None,
                "proof": {"name": "P", "version": v, "versions": 2, "pages": 1, "decision": {"name": "decisionApprovedWithChanges"}}}
    if method == "versions":
        return {"items": [{"version": 2, "token": "PROOFTOKEN0000000000000000000000", "created": 1790876598, "mime": "application/pdf", "commentsCount": 1, "repliesCount": 0, "isProcessed": True},
                          {"version": 1, "token": "TOK1", "created": 1789142028, "mime": "proofhq/combined", "commentsCount": 2, "repliesCount": 3, "isProcessed": True}]}
    if method == "recipients":
        return {"items": [{"name": "Copy", "isActive": True, "deadline": 1790884800, "decision": None,
                           "items": [{"name": "Kim", "roleName": "roleReviewerApprover", "decision": {"name": "decisionNotRelevant"}, "decisionAt": 0, "isPrimaryDecisionMaker": False, "commentsCount": 0}]}]}
    sid = kw["sessionId"]
    return {"items": [{"number": 1, "page": 1, "author": "A", "text": f"from {sid}", "isResolved": False}]}


api.rpc = fake_versions
vs = versions_cmd.run(URL)
assert vs["linkOpens"] == 2 and [v["version"] for v in vs["versions"]] == [1, 2] and vs["versions"][0]["file"] == "proofhq/combined"
assert list_cmd.run(URL, False, version=1)["comments"][0]["text"] == "from s1"  # read through version 1's own session
assert list_cmd.run(URL, False, version=2)["version"] == 2  # the link's own version: no switch
try:
    list_cmd.run(URL, False, version=7)
    raise AssertionError("unknown version must refuse")
except SystemExit:
    pass
rv = reviewers_cmd.run(URL)
assert rv["decision"] == "Approved with changes" and rv["stages"][0]["decision"] is None
assert rv["stages"][0]["reviewers"][0] == {"name": "Kim", "role": "Reviewer approver", "decision": "Not relevant", "decidedAt": None, "primaryDecisionMaker": False, "comments": 0}
print("ok")
