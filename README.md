# skills

Agent skills in the [Agent Skills](https://agentskills.io) format: one folder per skill under `skills/`, each with a `SKILL.md`. They install into any supported coding agent with the skills CLI.

## Install

```bash
npx skills add syantra/skills --skill workfront-proof -g -a claude-code   # or --skill snapseq, --skill pdf-merge
```

`-g` installs for the user rather than the current project; drop `-a` to be asked which agents. Later, `npx skills check` reports a newer version and `npx skills update` applies it.

## Skills

| Skill | What it does |
| --- | --- |
| [pdf-merge](skills/pdf-merge/SKILL.md) | Merges PDFs and images (JPEG, PNG, TIFF, WebP) into one PDF in a chosen order: each page keeps its own size, images go in without loss, and it never writes over an input. Needs `uv`. |
| [snapseq](skills/snapseq/SKILL.md) | Sets up and runs a snapseq screenshot capture set: assesses the directory (a repo, a monorepo app, or nothing), scaffolds the config, writes the spec and the capture from a proof, a PDF or a route list, runs it and checks the shots. Needs `uv` and Node. |
| [workfront-proof](skills/workfront-proof/SKILL.md) | Works through an Adobe Workfront proof like a contractor: lists review comments with the marked area as an image, describes the proof page by page, reads versions and sign-off, and replies or resolves on request. Needs `uv`. |

## Develop

A skill's tests live in `skills/<name>/tests/` as standalone scripts that run offline against a fake API; the root `tests/` holds checks on the repo as a whole. Run every test, then validate every skill's format:

```bash
./test.sh
```

A release covers the whole repo: `gh release create v<version> --title "v<version>" --notes "<what changed, per skill>"` on `main`. `metadata.version` in a `SKILL.md` is that skill's own version and moves on its own. The skills CLI updates from the folders on `main` regardless; releases are the changelog.

Evals in `skills/<name>/evals/evals.json` use `<review-url>` placeholders. Keep a filled copy beside it as `evals.local.json`, which git ignores. `tests/test_private.py` fails if a real proof link, tenant id or proof token lands anywhere in the repo.
