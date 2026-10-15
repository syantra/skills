# /// script
# requires-python = ">=3.10"
# ///
"""Set up snapseq (scripted screenshots) in a project.

  snapseq_setup.py assess [dir]    print JSON: the app, package manager, machine, and a reuse / add-to / standalone verdict
  snapseq_setup.py init [--app DIR | --standalone DIR --host URL] [options]    write the config, edit package.json, install

Run `init --help` for the options. Never reads .env files.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

CONFIGS = [f"snapseq.config.{e}" for e in ("ts", "mts", "cts", "js", "mjs", "cjs")]
LOCKS = [("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("package-lock.json", "npm"), ("bun.lock", "bun"), ("bun.lockb", "bun")]
FRAMEWORKS = [("next", "next"), ("astro", "astro"), ("nuxt", "nuxt"), ("@remix-run/dev", "remix"), ("@sveltejs/kit", "sveltekit"), ("vite", "vite")]
DEFAULT_PORT = {"next": 3000, "nuxt": 3000, "remix": 3000, "astro": 4321, "vite": 5173, "sveltekit": 5173}
PORT_RES = [r"\bPORT=(\d+)", r"--port[ =](\d+)", r"-p (\d+)", r"PORT:-(\d+)", r":(\d{4,5})\b"]
DEPS = {"@playwright/test": "^1.59.1", "snapseq": "^0.3.0", "snapseq-label": "^0.1.0", "snapseq-pdf": "^0.1.0"}
FLOOR = {"@playwright/test": (1, 59), "snapseq": (0, 3)}  # what the generated config needs (label(), pdf())


def fail(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def read_json(p):
    try:
        d = json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def find_root(d):
    return next((p for p in [d, *d.parents] if (p / ".git").exists()), None)


def chain(d, root):
    """d and its ancestors up to root; every ancestor when there is no root."""
    up = [d, *d.parents]
    return up[: up.index(root) + 1] if root else up


def package_manager(d, root):
    dirs = chain(d, root)
    for p in dirs:
        for f, pm in LOCKS:
            if (p / f).exists():
                return pm
    for p in dirs:
        m = re.match(r"(pnpm|yarn|npm|bun)@", str(read_json(p / "package.json").get("packageManager") or ""))
        if m:
            return m[1]
    return None


def workspace_globs(d):
    """Workspace globs declared in d (pnpm-workspace.yaml or package.json); [] if `packages:` is there but unreadable, None if no workspace."""
    globs, on, declared = [], False, False
    y = d / "pnpm-workspace.yaml"
    for line in y.read_text().splitlines() if y.is_file() else []:
        line = re.sub(r"(^|\s)#.*", "", line).rstrip()
        m = re.match(r"packages:(.*)$", line)
        if m:
            on = declared = True
            flow = m[1].strip()  # `packages: ["a/*", "b/*"]`; a list over several lines is left unread
            if flow[:1] == "[" and flow[-1:] == "]":
                globs += [g for g in (x.strip(" '\"") for x in flow[1:-1].split(",")) if g]
        elif on:
            if line[:1] not in ("", " ", "\t", "-"):  # next top-level key
                break
            m = re.match(r"^\s*-\s*['\"]?([^'\"]+?)['\"]?$", line)
            if m:
                globs.append(m[1])
    if not globs:
        ws = read_json(d / "package.json").get("workspaces")
        ws = ws.get("packages") if isinstance(ws, dict) else ws
        globs = [g for g in ws if isinstance(g, str)] if isinstance(ws, list) else []
    return globs or ([] if declared else None)


def port_of(dev, framework):
    dev = re.sub(r"--inspect(?:-brk)?(?:=\S*)?", "", dev or "")  # its :9229 is not the app's port
    for r in PORT_RES:
        m = re.search(r, dev)
        if m:
            return int(m[1])
    return DEFAULT_PORT.get(framework)


def app_record(d, base):
    p = read_json(d / "package.json")
    deps = {**p.get("dependencies", {}), **p.get("devDependencies", {})}
    scripts = p.get("scripts", {})
    framework = next((name for dep, name in FRAMEWORKS if dep in deps), None)
    config = next((c for c in CONFIGS if (d / c).exists()), None)
    text = re.sub(r"(^|\s)//.*", "", (d / config).read_text(errors="ignore")) if config else ""  # not a // inside a URL
    m = re.search(r"""capturesDir\s*:\s*["'`]([^"'`]+)["'`]""", text)
    cap = d / (m[1] if m else "captures")

    def names(pat):
        rels = (f.relative_to(cap).as_posix() for f in cap.glob("**/*") if f.is_file())
        return sorted(re.sub(pat, "", r) for r in rels if re.search(pat, r))

    return {
        "dir": Path(os.path.relpath(d, base)).as_posix(),
        "name": p.get("name"),
        "framework": framework,
        "dev": scripts.get("dev"),
        "port": port_of(scripts.get("dev"), "vite" if framework == "remix" and "vite" in deps else framework),
        "snapseq": deps.get("snapseq"),
        "plugins": {k: v for k, v in deps.items() if k.startswith("snapseq-")},
        "playwright": deps.get("@playwright/test"),
        "config": config,
        "captures": names(r"\.capture\.[cm]?[jt]s$"),
        "sequences": names(r"\.sequence\.md$"),
        "screenshotScript": scripts.get("screenshot"),
    }


def node_version():
    try:
        return subprocess.run(["node", "-v"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def node22():
    """bin dir of the newest nvm Node 22, else 20."""
    nvm = Path(os.environ.get("NVM_DIR") or Path.home() / ".nvm") / "versions/node"
    for major in (22, 20):
        found = list(nvm.glob(f"v{major}.*"))
        if found:
            return str(max(found, key=lambda p: tuple(map(int, re.findall(r"\d+", p.name)))) / "bin")
    return None


def chromium():
    custom = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if custom and custom != "0":  # "0" means inside node_modules, which assess cannot see
        return any(Path(custom).glob("chromium-*"))
    home = Path.home()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
    else:
        base = home / ("Library/Caches" if sys.platform == "darwin" else ".cache")
    return any(base.glob("ms-playwright/chromium-*"))


def decide(apps, inside):
    """(verdict, app dir or None, choose list or None). The app we are inside wins."""
    here = [a for a in apps if inside(a)]
    if here:
        a = max(here, key=lambda a: len(a["dir"]))
        return ("reuse" if a["config"] else "add-to"), a["dir"], None
    for kind, cands in (("reuse", [a for a in apps if a["config"]]), ("add-to", apps)):
        if not cands:
            continue
        fw = [a for a in cands if a["framework"]] if kind == "add-to" else []
        one = cands if len(cands) == 1 else fw if len(fw) == 1 else None
        if one:
            return kind, one[0]["dir"], None
        return kind, None, [a["dir"] for a in fw or cands]
    return "standalone", None, None


def assess(args):
    d = Path(args.dir).resolve()
    if not d.is_dir():
        fail(f"not a directory: {d}")
    root = find_root(d)
    up = chain(d, root)
    ws = next(((p, g) for p in up if (g := workspace_globs(p)) is not None), None)
    nearest = next((p for p in up if (p / "package.json").is_file()), None)
    dirs = []
    if ws and ws[1]:
        wroot, globs = ws

        def expand(gs):
            return {p.parent for g in gs for p in wroot.glob((g.strip("/") or ".") + "/package.json")
                    if "node_modules" not in p.relative_to(wroot).parts}

        dirs = sorted(expand([g for g in globs if not g.startswith("!")]) - expand([g[1:] for g in globs if g.startswith("!")]))
    unread = ws is not None and not dirs  # `packages:` declared, but no package found through it
    if not dirs:
        dirs = [nearest] if nearest else []
    base = root or (ws[0] if ws else dirs[0] if dirs else d)
    apps = [app_record(p, base) for p in dirs]
    verdict, app, choose = decide(apps, lambda a: base / a["dir"] in up)
    if unread and nearest == ws[0]:  # do not guess the app
        app, choose = None, [a["dir"] for a in apps]
    out = {
        "dir": str(d),
        "root": str(root) if root else None,
        "packageManager": package_manager(d, root),
        "workspace": ws is not None,
        "apps": apps,
        "node": node_version(),
        "node22": node22(),
        "chromium": chromium(),
        "verdict": verdict,
        "app": app,
        "appPath": str(base / app) if app else None,
    }
    if choose:
        out["choose"] = choose
    print(json.dumps(out, indent=2))


def key(name):
    return name if re.fullmatch(r"[A-Za-z_$][\w$]*", name) else json.dumps(name)


def parse_device(spec):
    m = re.fullmatch(r"([^=\s/\\]+)=(\d+)x(\d+)(?:@(\d+(?:\.\d+)?))?(\+touch)?", spec)
    if not m or m[1] in (".", "..") or 0 in (int(m[2]), int(m[3]), float(m[4] or 1)):
        fail(f"bad --device {spec!r}; use name=WxH[@DPR][+touch], a name with no spaces or slashes, sizes above 0")
    name, w, h, dpr, touch = m.groups()
    opts = f"viewport: {{ width: {int(w)}, height: {int(h)} }}"
    opts += f", deviceScaleFactor: {float(dpr):g}" if dpr else ""
    opts += ", hasTouch: true" if touch else ""
    return f"{key(name)}: {{ {opts} }}"


def config_text(run, env, host, dev, devices):
    if dev:  # NULs keep the command on one line when wrapping
        intro = f"Starts `{dev.replace(' ', chr(0))}` on {host} unless a server already answers there, in which case that one is used."
    else:
        intro = f"Shoots {host}; there is no dev server here."
    note = textwrap.fill(f"{intro} Output lands in ./.screenshots/<run>/, which ignores itself. A shot that passes "
                         "`label` gets a strip above it, and each device folder gets a PDF beside it.", width=80,
                         initial_indent="// ", subsequent_indent="// ", break_long_words=False, break_on_hyphens=False)
    web = f", webServer: {json.dumps(dev)}" if dev else ""
    lines = [
        'import { defineConfig } from "snapseq";',
        'import { label } from "snapseq-label";',
        'import { pdf } from "snapseq-pdf";',
        "",
        f"// {run} screenshot{' --' if run == 'npm run' else ''} [filter] [--device <name>] [--headed|--ui]",  # npm eats flags without --
        note.replace("\0", " "),
        "",
        "export default defineConfig({",
        "  envs: {",
        f"    {key(env)}: {{ host: {json.dumps(host)}{web} }},",
        "  },",
    ]
    if devices:
        lines += ["  devices: {", *(f"    {d}," for d in devices), "  },"]
    return "\n".join([*lines, "  plugins: [label(), pdf()],", "});", ""])


def run_cmd(cmd, cwd, env=None):
    print(f"run: {' '.join(cmd)}  (in {cwd})", flush=True)
    exe = shutil.which(cmd[0], path=(env or os.environ).get("PATH"))
    if not exe:
        fail(f"{cmd[0]} not found on PATH", 127)
    rc = subprocess.run([exe, *cmd[1:]], cwd=cwd, env=env).returncode
    if rc:
        sys.exit(rc)


def write(path, text):
    Path(path).write_text(text)
    print(f"write: {path}")


def dump(pkg):
    return json.dumps(pkg, indent=2, ensure_ascii=False) + "\n"


def init(args):
    standalone = args.standalone is not None
    devices = [parse_device(s) for s in args.device or []]
    if standalone:
        if not args.host:
            fail("--standalone needs --host")
        d = Path(args.standalone).resolve()
        if d.exists() and (not d.is_dir() or any(d.iterdir())):
            fail(f"{d} already exists and is not empty")
        root = rec = pkg = None
    else:
        d = Path(args.app or ".").resolve()
        if not (d / "package.json").is_file():
            fail(f"no package.json in {d}")
        for c in CONFIGS:
            if (d / c).exists():
                fail(f"{d / c} already exists")
        try:
            pkg = json.loads((d / "package.json").read_text())
        except ValueError as e:
            fail(f"{d / 'package.json'}: {e}")
        current = pkg.get("scripts", {}).get("screenshot")
        if current is not None and not current.startswith("snapseq"):
            fail(f'scripts.screenshot is already "{current}"; rename that script, then run init again')
        root = find_root(d)
        rec = app_record(d, root or d)
    pm = args.pm or (None if standalone else package_manager(d, root)) or next((p for p in ("pnpm", "yarn", "npm") if shutil.which(p)), "pnpm")
    if not args.no_install and not shutil.which(pm):  # before anything is written
        fail(f"{pm} not found on PATH; install it, or pass --pm with one that is installed")
    run = "npm run" if pm == "npm" else pm
    host = args.host or (f"http://localhost:{rec['port']}" if rec["port"] else None)
    if not host:
        fail("no port found in the dev script; pass --host")
    dev = args.dev_command if args.dev_command is not None else (f"{run} dev" if rec and rec["dev"] else "")

    if standalone:
        d.mkdir(parents=True, exist_ok=True)
        write(d / "package.json", dump({
            "name": d.name, "private": True, "type": "module", "scripts": {"screenshot": "snapseq"},
            "devDependencies": dict(DEPS)}))
        write(d / ".gitignore", "node_modules/\n")
    write(d / "snapseq.config.ts", config_text(run, args.env or ("prod" if standalone else "dev"), host, dev, devices))
    if not (d / "captures").is_dir():
        (d / "captures").mkdir()
        print(f"mkdir: {d / 'captures'}")
    if not standalone:
        pkg.setdefault("scripts", {}).setdefault("screenshot", "snapseq")
        for name, ver in DEPS.items():
            sect = next((k for k in ("dependencies", "devDependencies") if name in pkg.get(k, {})), None)
            m = re.search(r"(\d+)\.(\d+)", str(pkg[sect][name])) if sect else None
            if sect is None:
                pkg.setdefault("devDependencies", {})[name] = ver
            elif m and (int(m[1]), int(m[2])) < FLOOR.get(name, (0, 0)):  # the config needs the floor, so raise it
                print(f"raise: {name} {pkg[sect][name]} -> {ver}")
                pkg[sect][name] = ver
        write(d / "package.json", dump(pkg))
    if args.no_install:
        return

    run_cmd([pm, "install"], d)
    browser = {"npm": ["npx"], "bun": ["bunx"]}.get(pm, [pm, "exec"]) + ["playwright", "install", "chromium"]
    env, node = None, node_version()
    if node and int(re.match(r"v(\d+)", node)[1]) >= 26:  # `playwright install` hangs on Node 26
        n22 = node22()
        if not (n22 and Path(n22).is_dir()):
            print(f"warning: {node} hangs `playwright install` and no Node 22 was found. Skipped the browser install; "
                  f"run `{' '.join(browser)}` under Node 22 yourself.", file=sys.stderr)
            return
        print(f"note: {node} hangs `playwright install`; using Node from {n22}")
        env = {**os.environ, "PATH": n22 + os.pathsep + os.environ.get("PATH", "")}
    run_cmd(browser, d, env)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("assess", help="inspect a directory, print JSON")
    a.add_argument("dir", nargs="?", default=".")
    a.set_defaults(fn=assess)
    i = sub.add_parser("init", help="write config, edit package.json, install")
    g = i.add_mutually_exclusive_group()
    g.add_argument("--app", metavar="DIR", help="app directory (default: cwd)")
    g.add_argument("--standalone", metavar="DIR", help="create a new project here; needs --host")
    i.add_argument("--host", help="env host (default: http://localhost:<port from the dev script>)")
    i.add_argument("--env", help="env name (default: dev for --app, prod for --standalone)")
    i.add_argument("--dev-command", help='webServer command; "" for none (default: "<pm> dev" when the app has a dev script)')
    i.add_argument("--device", action="append", metavar="SPEC", help="name=WxH[@DPR][+touch], repeatable; none keeps snapseq's defaults")
    i.add_argument("--pm", choices=["pnpm", "yarn", "npm", "bun"], help="package manager (default: detected, else the first of pnpm, yarn, npm on PATH)")
    i.add_argument("--no-install", action="store_true", help="write files only")
    i.set_defaults(fn=init)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
