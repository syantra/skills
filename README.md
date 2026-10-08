# skills

Agent skills in the [Agent Skills](https://agentskills.io) format: one folder per skill under `skills/`, each with a `SKILL.md`. They install into any supported coding agent with the skills CLI.

## Install

```bash
npx skills add syantra/skills --skill workfront-proof -g -a claude-code
```

`-g` installs for the user rather than the current project; drop `-a` to be asked which agents. Later, `npx skills check` reports a newer version and `npx skills update` applies it.

## Skills

| Skill | What it does |
| --- | --- |
| [workfront-proof](skills/workfront-proof/SKILL.md) | Works through an Adobe Workfront proof like a contractor: lists review comments with the marked area as an image, describes the proof page by page, reads versions and sign-off, and replies or resolves on request. Needs `uv`. |

## Develop

A skill's tests live in `skills/<name>/tests/` as standalone scripts that run offline against a fake API; the root `tests/` holds checks on the repo as a whole. Run every test, then validate every skill's format:

```bash
./test.sh
```

Evals in `skills/<name>/evals/evals.json` use `<review-url>` placeholders. Keep a filled copy beside it as `evals.local.json`, which git ignores. `tests/test_private.py` fails if a real proof link, tenant id or proof token lands anywhere in the repo.
