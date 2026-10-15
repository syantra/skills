"""The Workfront proof viewer's RPC (undocumented): review URLs, sessions, comments, permissions."""
import gzip
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RPC = "https://us.my.workfront.com/proof/rpc/index.php"
CODES = Path.home() / ".config/workfront-proof/codes.json"  # proof token -> reviewer code, written by login.py
# Comment and reply permission bits in the viewer: EDIT 1, DELETE 2, LOCK 4, SET_ACTION 8, RESOLVE 16, BE_UNREAD 32
CAN_DELETE, CAN_RESOLVE = 2, 16


class Refused(SystemExit):
    """Workfront answered a call with an error: an HTTP error status, or an error response."""


def parse_review_url(url):
    """Review URL -> (proof token, comment number or None, tenant id or None, reviewer code or None).

    .../proof/review/<hex>-<proofToken>-<suffix>?tcmsTenantId=<tenant>#token:<proofToken>,comment:3/
    Signed in, the viewer's fragment also carries the reviewer code: #proof:<code>,token:<proofToken>,...
    """
    u = urllib.parse.urlsplit(url)
    frag = dict(p.split(":", 1) for p in u.fragment.strip("/").split(",") if ":" in p)
    token = frag.get("token")
    if not token:
        m = re.fullmatch(r".*/proof/review/[^/-]+-(.+)-[^/-]+", u.path.rstrip("/"))
        if not m:
            raise SystemExit("That is not a proof review link. Open the proof in the proof viewer and copy its address bar URL.")
        token = m.group(1)
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
        raise Refused(f"Workfront refused {method} (HTTP {e.code}): {body[:300].decode(errors='replace')}")
    if "error" in str(result.get("responseClass", "")).lower():
        raise Refused(f"Workfront refused {method}: {json.dumps(result)[:300]}")
    return result


def saved_code(token):
    try:
        return json.loads(CODES.read_text()).get(token)
    except (FileNotFoundError, ValueError):
        return None


def session(url, identify=False, version=None):
    """Start a viewer session -> (token, comment number from the URL, tenant, startup response).

    Reads go anonymous first and fall back to a reviewer code when Workfront refuses that;
    identify=True (writes) tries the reviewer code first so they run as the user.
    version=N switches to that version of the same proof; each version has its own token.
    """
    token, comment, tenant, link = parse_review_url(url)
    start = startup(tenant, token, identify, link)
    if version and version != start["proof"]["version"]:
        items = rpc(tenant, "versions", sessionId=start["sessionId"], only_processed=False)["items"]
        v = next((v for v in items if v["version"] == version), None)
        if v is None:
            raise SystemExit(f"No version {version}. This proof has versions {sorted(x['version'] for x in items)}.")
        # the same reviewer, in the other version: a code saved for any version of this proof comes before the link's
        start = startup(tenant, v["token"], identify, *(saved_code(x["token"]) for x in items), link)
        token = v["token"]
    return token, comment, tenant, start


def startup(tenant, token, identify, *codes):
    """Open a session with the first credential Workfront accepts; raises the first refusal when none is.

    Credentials: the code saved for this token, then `codes` in the order given (other versions' saved codes, the link's), and anonymous.
    Writes try them in that order, so a pasted colleague's link does not post as them; reads try anonymous first.
    The viewer's fragment can carry a `proof:` value Workfront refuses as a code, so a refusal only moves on.
    """
    codes = [c for c in (saved_code(token), *codes) if c]
    first = None
    for code in dict.fromkeys(codes + [""] if identify else [""] + codes):
        try:
            return rpc(tenant, "startup", token=token, proofingCode=code)
        except Refused as e:
            first = first or e
    raise first


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
