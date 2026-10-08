"""The Workfront proof viewer's RPC (undocumented): review URLs, sessions, comments, permissions."""
import gzip
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RPC = "https://us.my.workfront.com/proof/rpc/index.php"
CODES = Path.home() / ".config/workfront-proof/codes.json"  # proof token -> reviewer code, written by login.py
# Comment and reply permission bits in the viewer: EDIT 1, DELETE 2, LOCK 4, SET_ACTION 8, RESOLVE 16, BE_UNREAD 32
CAN_DELETE, CAN_RESOLVE = 2, 16


def parse_review_url(url):
    """Review URL -> (proof token, comment number or None, tenant id or None, reviewer code or None).

    .../proof/review/<hex>-<proofToken>-<suffix>?tcmsTenantId=<tenant>#token:<proofToken>,comment:3/
    Signed in, the viewer's fragment also carries the reviewer code: #proof:<code>,token:<proofToken>,...
    """
    u = urllib.parse.urlsplit(url)
    frag = dict(p.split(":", 1) for p in u.fragment.strip("/").split(",") if ":" in p)
    segment = u.path.rstrip("/").split("/")[-1]
    token = frag.get("token") or segment.split("-", 1)[1].rsplit("-", 1)[0]
    comment = frag.get("comment", "").strip("/")
    tenant = urllib.parse.parse_qs(u.query).get("tcmsTenantId", [None])[0]
    return token, int(comment) if comment.isdigit() else None, tenant, frag.get("proof")


def rpc(tenant, method, **params):
    # The viewer posts a JSON body under a form content type; the server rejects a real form body.
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if tenant:
        headers["tcmstenantid"] = tenant
    req = urllib.request.Request(RPC, data=json.dumps({"method": method, **params}).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read()
        body = gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body  # error bodies come gzipped
        raise SystemExit(f"Workfront refused {method} (HTTP {e.code}): {body[:300].decode(errors='replace')}")
    if "error" in str(result.get("responseClass", "")).lower():
        raise SystemExit(f"Workfront refused {method}: {json.dumps(result)[:300]}")
    return result


def saved_code(token):
    try:
        return json.loads(CODES.read_text()).get(token)
    except (FileNotFoundError, ValueError):
        return None


def session(url, identify=False, version=None):
    """Start a viewer session -> (token, comment number from the URL, tenant, startup response).

    identify=True uses the reviewer code so writes run as the user.
    version=N switches to that version of the same proof; each version has its own token.
    """
    token, comment, tenant, code = parse_review_url(url)
    code = (code or saved_code(token) or "") if identify else ""
    start = rpc(tenant, "startup", token=token, proofingCode=code)
    if version and version != start["proof"]["version"]:
        items = rpc(tenant, "versions", sessionId=start["sessionId"], only_processed=False)["items"]
        v = next((v for v in items if v["version"] == version), None)
        if v is None:
            raise SystemExit(f"No version {version}. This proof has versions {sorted(x['version'] for x in items)}.")
        token = v["token"]
        start = rpc(tenant, "startup", token=token, proofingCode=(saved_code(token) or "") if identify else "")
    return token, comment, tenant, start


def open_proof(url, identify=False, version=None):
    """session() plus the comments of that version."""
    token, comment, tenant, start = session(url, identify, version)
    comments = rpc(tenant, "comments", sessionId=start["sessionId"])["items"]
    return token, comment, tenant, start, comments


def find_comment(comments, number):
    c = next((c for c in comments if c["number"] == number), None)
    if c is None:
        raise SystemExit(f"No comment {number}. This version has {sorted(x['number'] for x in comments)}.")
    return c
