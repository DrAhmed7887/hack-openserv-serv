#!/usr/bin/env bash
# Runs pytest and saves the real output as TDD evidence.
#   scripts/tdd_step.sh RED   NN_slug <pytest args...>   -> docs/red/NN_slug.RED.log
#   scripts/tdd_step.sh GREEN NN_slug <pytest args...>   -> docs/red/NN_slug.GREEN.log
# The log keeps the command, python version, exit code and full output. Local repo, home and temp paths are
# scrubbed by scripts/scrub_paths.py (<repo>, <home>, <tmp>).
set -u
phase="$1"; slug="$2"; shift 2
cd "$(dirname "$0")/.."
out="docs/red/${slug}.${phase}.log"
{
  echo "# ${phase} evidence: ${slug}"
  echo "# command: python3 -m pytest $*"
  echo "# python: $(python3 --version 2>&1)"
  python3 -m pytest "$@" 2>&1
  echo "# exit code: ${PIPESTATUS[0]}"
} | python3 scripts/scrub_paths.py "$(pwd)" > "$out"
code=$(grep '^# exit code:' "$out" | awk '{print $4}')
tail -n 25 "$out"
if [ "$phase" = "RED" ] && [ "$code" = "0" ]; then echo "!! RED run passed: the test proves nothing"; exit 9; fi
if [ "$phase" = "GREEN" ] && [ "$code" != "0" ]; then echo "!! GREEN run failed"; exit 8; fi
exit 0
