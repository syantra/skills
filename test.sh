#!/bin/sh
# Every skill's tests, then the repo-wide checks, then the format of every skill. Each test prints ok.
fail=0
for f in skills/*/tests/test_*.py tests/test_*.py; do
  if out=$(uv run "$f" 2>&1); then echo "ok    $f"; else echo "FAIL  $f"; echo "$out" | tail -20; fail=1; fi
done
for s in skills/*/; do uvx --from 'git+https://github.com/agentskills/agentskills#subdirectory=skills-ref' skills-ref validate "${s%/}" || fail=1; done
exit $fail
