#!/usr/bin/env bash
# check_doc_freshness.sh — report whether tech-summary docs still match the code.
#
# Reads frontmatter (verified_at_commit + sources) from docs/*.md and, for each,
# asks git whether any sourced file changed since the doc was verified.
#
#   FRESH     — no sourced file changed since verified_at_commit
#   STALE     — sourced files changed; the listed commits are what the doc hasn't accounted for
#   UNTRACKED — doc has no freshness frontmatter (not produced by /tech-summary)
#
# Usage:
#   check_doc_freshness.sh            # check all docs/*.md in the current repo
#   check_doc_freshness.sh docs/x.md  # check specific file(s)
#   check_doc_freshness.sh -v         # verbose: list the changed files/commits
#
# This script is bundled with the tech-summary-tools plugin, so it may run from
# a plugin cache directory rather than the target project. It always resolves
# paths against the caller's current working directory (the invoking repo),
# never against its own file location.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

VERBOSE=0
BUMP=0
FILES=()
for arg in "$@"; do
  case "$arg" in
    -v|--verbose) VERBOSE=1 ;;
    -b|--bump) BUMP=1 ;;
    *) FILES+=("$arg") ;;
  esac
done
HEAD_SHA="$(git rev-parse HEAD)"
TODAY="$(date +%F)"

# Roll a FRESH doc's marker forward to HEAD. Safe because FRESH proves no sourced
# file changed since verified_at_commit, so the verification still holds at HEAD.
bump_marker() {
  local doc="$1"
  sed -i \
    -e "s/^verified_at_commit:.*/verified_at_commit: ${HEAD_SHA}/" \
    -e "s/^last_verified:.*/last_verified: ${TODAY}/" \
    "$doc"
}
if [ ${#FILES[@]} -eq 0 ]; then
  mapfile -t FILES < <(find docs -maxdepth 1 -name '*.md' | sort)
fi

# Extract a scalar frontmatter value (first --- ... --- block).
frontmatter_value() {
  awk -v key="$1" '
    NR==1 && $0!="---" { exit }
    NR==1 { inside=1; next }
    inside && $0=="---" { exit }
    inside && $0 ~ "^"key":" { sub("^"key":[[:space:]]*",""); print; exit }
  ' "$2"
}

# Extract the YAML list under "sources:" (lines like "  - path/to/file").
frontmatter_sources() {
  awk '
    NR==1 && $0!="---" { exit }
    NR==1 { inside=1; next }
    inside && $0=="---" { exit }
    inside && $0 ~ /^sources:/ { collecting=1; next }
    collecting && $0 ~ /^[[:space:]]+-[[:space:]]/ { sub(/^[[:space:]]+-[[:space:]]*/,""); print; next }
    collecting && $0 ~ /^[^[:space:]]/ { collecting=0 }
  ' "$1"
}

stale=0; fresh=0; untracked=0
printf "%-48s %-10s %s\n" "DOC" "STATUS" "DETAIL"
printf "%-48s %-10s %s\n" "---" "------" "------"

for doc in "${FILES[@]}"; do
  [ -f "$doc" ] || continue
  commit="$(frontmatter_value verified_at_commit "$doc" || true)"
  if [ -z "$commit" ]; then
    printf "%-48s %-10s %s\n" "$doc" "UNTRACKED" "no freshness frontmatter"
    untracked=$((untracked+1)); continue
  fi
  if ! git cat-file -e "${commit}^{commit}" 2>/dev/null; then
    printf "%-48s %-10s %s\n" "$doc" "UNKNOWN" "commit $commit not found"
    continue
  fi

  mapfile -t sources < <(frontmatter_sources "$doc")
  if [ ${#sources[@]} -eq 0 ]; then
    printf "%-48s %-10s %s\n" "$doc" "UNTRACKED" "no sources listed"
    untracked=$((untracked+1)); continue
  fi

  changed_count=$(git log --oneline "${commit}..HEAD" -- "${sources[@]}" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$changed_count" -eq 0 ]; then
    if [ "$BUMP" -eq 1 ] && [ "$commit" != "$HEAD_SHA" ]; then
      bump_marker "$doc"
      printf "%-48s %-10s %s\n" "$doc" "FRESH" "marker advanced to ${HEAD_SHA:0:9}"
    else
      printf "%-48s %-10s %s\n" "$doc" "FRESH" "verified @ ${commit:0:9}"
    fi
    fresh=$((fresh+1))
  else
    changed_files=$(git diff --name-only "${commit}..HEAD" -- "${sources[@]}" 2>/dev/null | xargs -n1 basename 2>/dev/null | paste -sd, -)
    printf "%-48s %-10s %s\n" "$doc" "STALE" "$changed_count commit(s) since verify ($changed_files)"
    stale=$((stale+1))
    if [ "$VERBOSE" -eq 1 ]; then
      git log --oneline "${commit}..HEAD" -- "${sources[@]}" | sed 's/^/    /'
    fi
  fi
done

echo
echo "Summary: $fresh fresh, $stale stale, $untracked untracked"
[ "$stale" -eq 0 ]
