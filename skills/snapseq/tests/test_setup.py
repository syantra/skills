# /// script
# requires-python = ">=3.10"
# ///
"""Offline check for snapseq_setup.py: assess verdicts and init output on fixture projects.

Run: uv run skills/snapseq/tests/test_setup.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "snapseq_setup.py"


def w(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def pkg(d, **fields):
    w(d / "package.json", json.dumps(fields))


def env_for(home, **extra):  # an empty HOME: no nvm, no browser cache, whatever the machine has
    base = {k: v for k, v in os.environ.items() if k not in ("NVM_DIR", "PLAYWRIGHT_BROWSERS_PATH")}
    return {**base, "HOME": str(home), "USERPROFILE": str(home), "LOCALAPPDATA": str(home), **extra}


def script(*args, env, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], env=env, cwd=cwd, capture_output=True, text=True)


with tempfile.TemporaryDirectory() as t:
    tmp = Path(t).resolve()
    home = tmp / "home"
    home.mkdir()
    nobin = tmp / "nobin"  # an empty PATH: no package manager unless a test adds one
    nobin.mkdir()
    ENV = env_for(home, PATH=str(nobin))

    def assess(d):
        r = script("assess", str(d), env=ENV)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)

    # 1. pnpm monorepo: one app has a config, so assess reuses it from the root; inside another app, that app wins.
    mono = tmp / "mono"
    (mono / ".git").mkdir(parents=True)
    w(mono / "pnpm-lock.yaml")
    w(mono / "pnpm-workspace.yaml", 'packages:\n  - "apps/*"\n  - "packages/*"\n  - "!apps/retired"\n\nallowBuilds:\n  esbuild: true\n\n'
      "onlyBuiltDependencies:\n  - esbuild\n")
    pkg(mono / "apps/retired", name="retired", dependencies={"next": "15.0.0"})  # excluded by the workspace
    w(mono / "apps/retired/snapseq.config.ts", "export default {};\n")
    pkg(mono / "esbuild")  # would show up as an app if the list ran on past `packages:`
    pkg(mono / "apps/shop", name="shop", dependencies={"next": "16.0.0"},
        scripts={"dev": "next dev --port ${PORT:-3002}", "screenshot": "snapseq"},
        devDependencies={"snapseq": "^0.1.0", "@playwright/test": "1.59.1", "snapseq-label": "^0.1.0"})
    w(mono / "apps/shop/snapseq.config.ts", "export default {};\n")
    w(mono / "apps/shop/captures/root.capture.ts")
    w(mono / "apps/shop/captures/root.sequence.md")
    w(mono / "apps/shop/captures/helpers/keys.ts")
    w(mono / "apps/shop/captures/campaign/pricing.capture.ts")
    pkg(mono / "apps/web", name="web", dependencies={"next": "16.0.0"}, scripts={"dev": "next dev"})
    pkg(mono / "packages/ui", name="@repo/ui")
    a = assess(mono)
    assert a["dir"] == str(mono) and a["root"] == str(mono)
    assert a["packageManager"] == "pnpm" and a["workspace"] is True
    assert (a["verdict"], a["app"], a["appPath"]) == ("reuse", "apps/shop", str(mono / "apps/shop")) and "choose" not in a
    assert a["node22"] is None and a["chromium"] is False
    by = {x["dir"]: x for x in a["apps"]}
    assert list(by) == ["apps/shop", "apps/web", "packages/ui"], list(by)
    assert by["apps/shop"] == {
        "dir": "apps/shop", "name": "shop", "framework": "next", "dev": "next dev --port ${PORT:-3002}", "port": 3002,
        "snapseq": "^0.1.0", "plugins": {"snapseq-label": "^0.1.0"}, "playwright": "1.59.1", "config": "snapseq.config.ts",
        "captures": ["campaign/pricing", "root"], "sequences": ["root"], "screenshotScript": "snapseq"}
    assert (by["apps/web"]["port"], by["apps/web"]["config"], by["apps/web"]["captures"]) == (3000, None, [])
    assert (by["packages/ui"]["framework"], by["packages/ui"]["port"]) == (None, None)
    b = assess(mono / "apps/web")
    assert b["dir"] == str(mono / "apps/web") and (b["verdict"], b["app"], b["appPath"]) == ("add-to", "apps/web", str(mono / "apps/web"))
    assert (assess(mono / "apps/shop/captures")["verdict"], assess(mono / "packages")["app"]) == ("reuse", "apps/shop")

    # 2. single yarn app, no config.
    site = tmp / "site"
    (site / ".git").mkdir(parents=True)
    w(site / "yarn.lock")
    pkg(site, name="site", dependencies={"next": "16.0.0"}, scripts={"dev": "next dev"})
    a = assess(site)
    assert (a["packageManager"], a["workspace"], a["verdict"], a["app"], a["appPath"]) == ("yarn", False, "add-to", ".", str(site))
    # an explicit PORT= beats the framework default.
    ported = tmp / "ported"
    pkg(ported, name="ported", dependencies={"next": "16.0.0"}, scripts={"dev": "PORT=4000 next dev"})
    assert assess(ported)["apps"][0]["port"] == 4000
    # an --inspect address is not the app's port, and Remix on vite serves on 5173.
    insp = tmp / "insp"
    pkg(insp, name="insp", dependencies={"next": "16.0.0"}, scripts={"dev": "NODE_OPTIONS=--inspect=127.0.0.1:9229 next dev"})
    rmx = tmp / "rmx"
    pkg(rmx, name="rmx", dependencies={"@remix-run/dev": "2.0.0"}, devDependencies={"vite": "6.0.0"}, scripts={"dev": "remix vite:dev"})
    assert (assess(insp)["apps"][0]["port"], assess(rmx)["apps"][0]["port"]) == (3000, 5173)
    assert (a["apps"][0]["port"], a["apps"][0]["framework"], a["apps"][0]["config"], a["apps"][0]["captures"]) == (3000, "next", None, [])

    # 3. nothing to attach to.
    empty = tmp / "empty"
    (empty / ".git").mkdir(parents=True)
    a = assess(empty)
    assert (a["verdict"], a["apps"], a["app"], a["root"]) == ("standalone", [], None, str(empty))
    bare = tmp / "bare"
    bare.mkdir()
    a = assess(bare)
    assert (a["verdict"], a["apps"], a["app"], a["root"], a["packageManager"]) == ("standalone", [], None, None, None)
    # without .git, the enclosing package is still found from a subdirectory.
    loose = tmp / "loose"
    pkg(loose, name="loose", scripts={"screenshot": "snapseq"}, devDependencies={"snapseq": "^0.2.0"})
    w(loose / "snapseq.config.ts", "export default {};\n")
    (loose / "captures").mkdir()
    a = assess(loose / "captures")
    assert (a["root"], a["verdict"], a["app"], a["appPath"]) == (None, "reuse", ".", str(loose))

    # 4. two framework apps and no config: the user picks. A plain library is not a candidate.
    two = tmp / "two"
    (two / ".git").mkdir(parents=True)
    w(two / "package-lock.json")
    pkg(two, name="root", workspaces=["apps/*", "packages/*"])
    pkg(two / "apps/site", name="site", dependencies={"astro": "5.0.0"})
    pkg(two / "apps/admin", name="admin", devDependencies={"vite": "7.0.0"})
    pkg(two / "packages/ui", name="ui")
    a = assess(two)
    assert (a["packageManager"], a["workspace"]) == ("npm", True)
    assert (a["verdict"], a["app"], a["choose"]) == ("add-to", None, ["apps/admin", "apps/site"])
    assert [(x["framework"], x["port"]) for x in a["apps"] if x["dir"] != "packages/ui"] == [("vite", 5173), ("astro", 4321)]
    # exactly one framework app wins, and workspaces may be {packages: [...]}.
    one = tmp / "one"
    (one / ".git").mkdir(parents=True)
    pkg(one, name="root", packageManager="bun@1.2.0", workspaces={"packages": ["apps/*", "libs/*"]})
    pkg(one / "apps/site", name="site", dependencies={"@sveltejs/kit": "2.0.0"})
    pkg(one / "libs/ui", name="ui")
    a = assess(one)
    assert (a["packageManager"], a["verdict"], a["app"], "choose" in a) == ("bun", "add-to", "apps/site", False)
    # pnpm-workspace.yaml: a comment after a glob or after `packages:`, and a flow list, still count.
    for name, yaml in (("wcomment", 'packages:  # apps\n  - apps/web   # the site\n  - "libs/*"  # shared\n'),
                       ("wflow", "packages: ['apps/*', \"libs/*\"]  # inline\n")):
        wd = tmp / name
        (wd / ".git").mkdir(parents=True)
        w(wd / "pnpm-workspace.yaml", yaml)
        pkg(wd / "apps/web", name="web", dependencies={"next": "16.0.0"})
        pkg(wd / "libs/ui", name="ui")
        assert [x["dir"] for x in assess(wd)["apps"]] == ["apps/web", "libs/ui"], name
    # a `packages:` list it cannot read is no reason to pick an app: the user chooses.
    wodd = tmp / "wodd"
    (wodd / ".git").mkdir(parents=True)
    w(wodd / "pnpm-workspace.yaml", 'packages: [\n  "apps/*",\n]\n')
    pkg(wodd, name="root")
    pkg(wodd / "apps/web", name="web", dependencies={"next": "16.0.0"})
    a = assess(wodd)
    assert (a["workspace"], a["app"], a["appPath"], a["choose"]) == (True, None, None, ["."])
    # a glob that expands to nothing is as unreadable as no glob.
    wbrace = tmp / "wbrace"
    (wbrace / ".git").mkdir(parents=True)
    w(wbrace / "pnpm-workspace.yaml", 'packages: ["{apps,libs}/*"]\n')
    pkg(wbrace, name="root")
    pkg(wbrace / "apps/web", name="web", dependencies={"next": "16.0.0"})
    a = assess(wbrace)
    assert (a["app"], a["choose"]) == (None, ["."])
    # capturesDir comes from the config, and every extension snapseq matches counts.
    cd = tmp / "cd"
    pkg(cd, name="cd", scripts={"screenshot": "snapseq"})
    w(cd / "snapseq.config.ts", 'export default defineConfig({\n  // capturesDir: "old",\n'
      '  envs: { prod: { host: "https://x.test" } }, capturesDir: "shots",\n});\n')  # a commented one is ignored, a URL is not a comment
    for f in ("shots/a.capture.mjs", "shots/sub/b.capture.cts", "shots/c.capture.ts", "shots/x.sequence.md", "shots/helper.ts",
              "captures/old.capture.ts"):
        w(cd / f)
    r = assess(cd)["apps"][0]
    assert (r["captures"], r["sequences"]) == (["a", "c", "sub/b"], ["x"]), r

    # 5. init in an app.
    before = {p.name for p in site.iterdir()}
    r = script("init", "--app", str(site), "--no-install", env=ENV)
    assert r.returncode == 0, r.stderr
    cfg = (site / "snapseq.config.ts").read_text()
    assert cfg == """import { defineConfig } from "snapseq";
import { label } from "snapseq-label";
import { pdf } from "snapseq-pdf";

// yarn screenshot [filter] [--device <name>] [--headed|--ui]
// Starts `yarn dev` on http://localhost:3000 unless a server already answers
// there, in which case that one is used. Output lands in ./.screenshots/<run>/,
// which ignores itself. A shot that passes `label` gets a strip above it, and
// each device folder gets a PDF beside it.

export default defineConfig({
  envs: {
    dev: { host: "http://localhost:3000", webServer: "yarn dev" },
  },
  plugins: [label(), pdf()],
});
""", cfg
    assert all(len(line) <= 80 for line in cfg.splitlines())
    assert (site / "captures").is_dir()
    p = json.loads((site / "package.json").read_text())
    assert p["scripts"] == {"dev": "next dev", "screenshot": "snapseq"}
    assert p["devDependencies"] == {"@playwright/test": "^1.59.1", "snapseq": "^0.3.0", "snapseq-label": "^0.1.0", "snapseq-pdf": "^0.1.0"}
    assert p["dependencies"] == {"next": "16.0.0"}
    assert str(site / "snapseq.config.ts") in r.stdout and "run:" not in r.stdout
    pkg_text = (site / "package.json").read_text()
    again = script("init", "--app", str(site), "--no-install", env=ENV)
    assert again.returncode == 1 and "already exists" in again.stderr
    assert (site / "snapseq.config.ts").read_text() == cfg and (site / "package.json").read_text() == pkg_text
    assert {p.name for p in site.iterdir()} == before | {"snapseq.config.ts", "captures"}
    # an app with a screenshot script keeps it; packages below what the config needs are raised where they sit.
    kept = tmp / "kept"
    pkg(kept, name="kept", scripts={"screenshot": "snapseq --headed"}, dependencies={"snapseq": "^0.1.0"},
        devDependencies={"@playwright/test": "1.50.0"})
    r = script("init", "--app", str(kept), "--host", "http://localhost:4000", "--no-install", env=ENV)
    assert r.returncode == 0, r.stderr
    p = json.loads((kept / "package.json").read_text())
    assert (p["scripts"], p["dependencies"], p["devDependencies"]) == (
        {"screenshot": "snapseq --headed"}, {"snapseq": "^0.3.0"},
        {"@playwright/test": "^1.59.1", "snapseq-label": "^0.1.0", "snapseq-pdf": "^0.1.0"})
    assert "raise: snapseq ^0.1.0 -> ^0.3.0" in r.stdout
    # at or above that, they stay.
    newer = tmp / "newer"
    pkg(newer, name="newer", dependencies={"snapseq": "^0.4.0"}, devDependencies={"@playwright/test": "1.60.2"})
    assert script("init", "--app", str(newer), "--host", "http://localhost:4000", "--no-install", env=ENV).returncode == 0
    p = json.loads((newer / "package.json").read_text())
    assert (p["dependencies"], p["devDependencies"]["@playwright/test"]) == ({"snapseq": "^0.4.0"}, "1.60.2")
    assert 'dev: { host: "http://localhost:4000" }' in (kept / "snapseq.config.ts").read_text()  # no dev script, no webServer
    # a screenshot script that runs another tool is a conflict, reported before anything is written.
    taken = tmp / "taken"
    pkg(taken, name="taken", scripts={"screenshot": "node shoot.js"})
    r = script("init", "--app", str(taken), "--host", "http://localhost:4000", "--no-install", env=ENV)
    assert r.returncode == 1 and "node shoot.js" in r.stderr and not (taken / "snapseq.config.ts").exists()

    # 6. init standalone, with devices.
    shots = tmp / "site-shots"
    r = script("init", "--standalone", str(shots), "--host", "https://www.example.com", "--device", "desktop=1728x890@2",
               "--device", "mobile=430x803@2+touch", "--no-install", env=ENV)
    assert r.returncode == 0, r.stderr
    assert json.loads((shots / "package.json").read_text()) == {
        "name": "site-shots", "private": True, "type": "module", "scripts": {"screenshot": "snapseq"},
        "devDependencies": {"@playwright/test": "^1.59.1", "snapseq": "^0.3.0", "snapseq-label": "^0.1.0", "snapseq-pdf": "^0.1.0"}}
    assert (shots / ".gitignore").read_text() == "node_modules/\n"
    cfg = (shots / "snapseq.config.ts").read_text()
    assert cfg == """import { defineConfig } from "snapseq";
import { label } from "snapseq-label";
import { pdf } from "snapseq-pdf";

// pnpm screenshot [filter] [--device <name>] [--headed|--ui]
// Shoots https://www.example.com; there is no dev server here. Output lands in
// ./.screenshots/<run>/, which ignores itself. A shot that passes `label` gets
// a strip above it, and each device folder gets a PDF beside it.

export default defineConfig({
  envs: {
    prod: { host: "https://www.example.com" },
  },
  devices: {
    desktop: { viewport: { width: 1728, height: 890 }, deviceScaleFactor: 2 },
    mobile: { viewport: { width: 430, height: 803 }, deviceScaleFactor: 2, hasTouch: true },
  },
  plugins: [label(), pdf()],
});
""", cfg
    assert (shots / "captures").is_dir()
    assert script("init", "--standalone", str(shots), "--host", "https://x.test", "--no-install", env=ENV).returncode == 1  # not empty
    assert script("init", "--standalone", str(tmp / "nohost"), "--no-install", env=ENV).returncode == 1
    assert not (tmp / "nohost").exists()
    for bad in ("tv=wide", "tv=0x844", "tv=390x0", "tv=390x844@0", "..=390x844", ".=390x844", "a/b=390x844", "=390x844"):
        r = script("init", "--standalone", str(tmp / "baddev"), "--host", "https://x.test", "--device", bad, "--no-install", env=ENV)
        assert r.returncode == 1 and not (tmp / "baddev").exists(), bad
    # leading zeros are plain numbers in the config.
    norm = tmp / "norm"
    r = script("init", "--standalone", str(norm), "--host", "https://x.test", "--device", "m-1=0390x0844@02.50+touch", "--device", "4k=3840x2160", "--no-install", env=ENV)
    assert r.returncode == 0, r.stderr
    assert '"m-1": { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2.5, hasTouch: true },' in (norm / "snapseq.config.ts").read_text()
    assert '"4k": { viewport: { width: 3840, height: 2160 } },' in (norm / "snapseq.config.ts").read_text()  # a digit first is fine

    # 7. init needs a package.json, and a host it can find.
    nopkg = tmp / "nopkg"
    nopkg.mkdir()
    assert script("init", "--app", str(nopkg), "--no-install", env=ENV).returncode != 0
    assert list(nopkg.iterdir()) == []
    noport = tmp / "noport"
    pkg(noport, name="noport", scripts={"dev": "node server.js"})
    r = script("init", "--app", str(noport), "--no-install", env=ENV)
    assert r.returncode == 1 and "--host" in r.stderr and not (noport / "snapseq.config.ts").exists()

    # 8. A package manager that is not installed is found out before anything is written; with none given, the first installed one is used.
    nvm_dir = tmp / "customnvm"
    (nvm_dir / "versions/node/v22.5.0/bin").mkdir(parents=True)
    out = json.loads(script("assess", str(tmp), env=env_for(home, NVM_DIR=str(nvm_dir))).stdout)
    assert out["node22"] == str(nvm_dir / "versions/node/v22.5.0/bin")  # $NVM_DIR is honoured
    browsers = tmp / "browsers"
    (browsers / "chromium-1169").mkdir(parents=True)
    assert json.loads(script("assess", str(tmp), env=env_for(home, PLAYWRIGHT_BROWSERS_PATH=str(browsers))).stdout)["chromium"] is True
    if os.name == "posix":
        def bins(name, *tools):
            b = tmp / name
            for t in tools:
                w(b / t, "#!/bin/sh\n")
                (b / t).chmod(0o755)
            return b

        npm_only = env_for(home, PATH=str(bins("npmbin", "npm")))
        yarn_npm = env_for(home, PATH=str(bins("yarnbin", "yarn", "npm")))
        for name, env, line in (("pick-npm", npm_only, "// npm run screenshot -- [filter] [--device <name>] [--headed|--ui]"),
                                ("pick-yarn", yarn_npm, "// yarn screenshot [filter] [--device <name>] [--headed|--ui]")):
            r = script("init", "--standalone", str(tmp / name), "--host", "https://x.test", "--no-install", env=env)
            assert r.returncode == 0 and line in (tmp / name / "snapseq.config.ts").read_text(), r.stderr
        for name, extra, env in (("none", [], ENV), ("wrong-pm", ["--pm", "yarn"], npm_only)):
            r = script("init", "--standalone", str(tmp / name), "--host", "https://x.test", *extra, env=env)
            assert r.returncode == 1 and "not found on PATH" in r.stderr and not (tmp / name).exists(), (name, r.stderr)

    # 9. Node 26 hangs `playwright install`: run it under the newest Node 22, or skip it with a warning.
    if os.name == "posix":
        fake = tmp / "fakebin"
        w(fake / "node", "#!/bin/sh\necho v26.1.0\n")
        w(fake / "pnpm", '#!/bin/sh\necho "pnpm $* PATH=$PATH"\n')
        for f in fake.iterdir():
            f.chmod(0o755)
        nvm = tmp / "nvmhome/.nvm/versions/node"
        for v in ("v22.3.0", "v22.11.0", "v20.9.0"):
            (nvm / v / "bin").mkdir(parents=True)
        n22 = str(nvm / "v22.11.0/bin")
        fake_path = f"{fake}{os.pathsep}{os.environ['PATH']}"
        env26 = env_for(tmp / "nvmhome", PATH=fake_path)
        assert json.loads(script("assess", str(tmp), env=env26).stdout)["node22"] == n22  # 22.11 beats 22.3
        app = tmp / "p26"
        pkg(app, name="p26", scripts={"dev": "next dev"}, dependencies={"next": "16.0.0"})
        w(app / "pnpm-lock.yaml")
        r = script("init", "--app", str(app), "--host", "http://localhost:3000", env=env26)
        assert r.returncode == 0, r.stderr
        ran = [line for line in r.stdout.splitlines() if line.startswith("pnpm ")]
        assert len(ran) == 2 and ran[0].startswith("pnpm install PATH=") and n22 not in ran[0], ran
        assert ran[1].startswith(f"pnpm exec playwright install chromium PATH={n22}{os.pathsep}"), ran
        app2 = tmp / "p26b"
        pkg(app2, name="p26b", scripts={"dev": "next dev"}, dependencies={"next": "16.0.0"})
        w(app2 / "pnpm-lock.yaml")
        r = script("init", "--app", str(app2), "--host", "http://localhost:3000", env=env_for(home, PATH=fake_path))
        ran = [line for line in r.stdout.splitlines() if line.startswith("pnpm ")]
        assert r.returncode == 0 and len(ran) == 1 and ran[0].startswith("pnpm install"), (r.stdout, r.stderr)
        assert "Node 22" in r.stderr and "playwright install chromium" in r.stderr

print("ok")
