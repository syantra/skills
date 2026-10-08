# /// script
# requires-python = ">=3.10"
# ///
"""No real proof in the repo: review links use a placeholder host, tenant and token, and no proof token appears on its own.

Run: uv run tests/test_private.py
"""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
ok_hosts = {"TENANT", "example"}
bad = []
for p in sorted(root.rglob("*")):
    if p.suffix not in {".py", ".md", ".json"} or {".venv", "__pycache__"} & set(p.parts) or p.name.endswith(".local.json"):
        continue
    s = p.read_text(errors="replace")
    for host, token in re.findall(r"https?://([\w.-]+)/proof/review/[0-9a-f]{32}-([A-Za-z0-9]{32})-", s):
        if host.split(".")[0] not in ok_hosts or not token.startswith("PROOFTOKEN"):
            bad.append(f"{p.relative_to(root)}: review link for {host}")
    bad += [f"{p.relative_to(root)}: tenant id {t}" for t in re.findall(r"tcmsTenantId=([0-9a-f]{32})", s) if t.strip("0")]
    # A proof token is 32 alphanumerics with upper, lower and digits mixed; the placeholder has no lowercase.
    bad += [f"{p.relative_to(root)}: token {w}" for w in re.findall(r"\b[A-Za-z0-9]{32}\b", s)
            if re.search("[a-z]", w) and re.search("[A-Z]", w) and re.search("[0-9]", w)]
assert not bad, "real proof identifiers found:\n" + "\n".join(bad)
print("ok")
