#!/usr/bin/env bash
# jd.sh - fetch a LinkedIn job posting through the fetch-jd workflow and build
# the one-click-copy page. Works from any checkout: it operates in a temporary
# worktree of the utility branch and never touches the current branch.
#
#   .github/scripts/jd.sh <linkedin job url | numeric id> [out.html]
set -euo pipefail

BRANCH="claude/linkedin-jd-extraction-da822a"
arg="${1:?usage: jd.sh <linkedin job url or id> [out.html]}"
id="$(printf '%s' "$arg" | grep -oE '[0-9]{6,}' | head -n1 || true)"
[ -n "$id" ] || { echo "jd.sh: no numeric job id in '$arg'" >&2; exit 1; }
out="${2:-${TMPDIR:-/tmp}/jd-$id.html}"

root="$(git rev-parse --show-toplevel)"
wt="$(mktemp -d)"
cleanup() { cd "$root" && git worktree remove --force "$wt" 2>/dev/null || true; }
trap cleanup EXIT
t0=$(date +%s.%N)

git fetch -q origin "$BRANCH"
git worktree add -q --detach "$wt" "origin/$BRANCH"
cd "$wt"

printf '%s\n# requested %s\n' "$id" "$(date -u +%FT%TZ)" > jd/REQUEST
git add jd/REQUEST
git -c user.name=Claude -c user.email=noreply@anthropic.com commit -q -m "chore(jd): request posting $id"
git push -q origin "HEAD:refs/heads/$BRANCH"
mine="$(git rev-parse HEAD)"
t1=$(date +%s.%N)
echo "jd.sh: pushed request $id (${mine:0:7}); waiting for the runner"

deadline=$(( $(date +%s) + 240 ))
while :; do
  head="$(git ls-remote -q origin "refs/heads/$BRANCH" | cut -f1 || true)"
  if [ -n "$head" ] && [ "$head" != "$mine" ]; then
    git fetch -q origin "$BRANCH"
    if git merge-base --is-ancestor "$mine" "origin/$BRANCH" \
       && git log -1 --format=%s "origin/$BRANCH" | grep -q "fetched LinkedIn posting $id"; then
      break
    fi
  fi
  [ "$(date +%s)" -lt "$deadline" ] || { echo "jd.sh: timed out waiting for the fetch-jd run" >&2; exit 2; }
  sleep 1
done
t2=$(date +%s.%N)
git checkout -q --detach "origin/$BRANCH"

python3 .github/scripts/build_jd_page.py "jd/$id/job.json" "$out"
python3 - "jd/$id/job.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])); j = d["job"]
print(f"jd.sh: {j.get('title')} | {j.get('company')} | {j.get('location')} | via {d['source']}")
PY
t3=$(date +%s.%N)

# keep a checkout of the utility branch current, if that is what the caller is on
cd "$root"
if [ "$(git rev-parse --abbrev-ref HEAD)" = "$BRANCH" ]; then
  git pull -q --ff-only origin "$BRANCH" || true
fi
python3 - "$t0" "$t1" "$t2" "$t3" <<'PY'
import sys; t0,t1,t2,t3 = map(float, sys.argv[1:])
print(f"jd.sh: push {t1-t0:.1f}s | runner {t2-t1:.1f}s | build {t3-t2:.1f}s | total {t3-t0:.1f}s")
PY
echo "jd.sh: page -> $out"
