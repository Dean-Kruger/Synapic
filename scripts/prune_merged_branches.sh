#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# prune_merged_branches.sh
# ------------------------
# Delete local branches that are fully merged into the current branch.
#
# Safety rules:
#   - Only branches reported by `git branch --merged` are considered, and
#     `git branch -d` (safe delete) is used, so branches with unmerged
#     commits are refused.
#   - The current branch and `main` are never deleted.
#   - Branches checked out in a linked worktree are skipped.
#
# Usage:
#   ./scripts/prune_merged_branches.sh [base-branch]
#
#   base-branch defaults to the current branch (e.g. `main`).
#   Use `--dry-run` to list what would be deleted without deleting.
# ---------------------------------------------------------------------------
set -euo pipefail

base="${1:-}"
dry_run=false
if [[ "${base}" == "--dry-run" ]]; then
  dry_run=true
  base="$(git branch --show-current)"
fi
if [[ -z "${base}" ]]; then
  base="$(git branch --show-current)"
fi

# Refresh remote-tracking refs so `--merged` reflects the latest remote state.
git fetch --prune origin 2>/dev/null || true

echo "Pruning local branches merged into '${base}'..."

protected="^(main|HEAD|${base})$"
deleted=0
skipped=0

while IFS= read -r branch; do
  [[ -z "${branch}" ]] && continue
  if [[ "${branch}" =~ ${protected} ]]; then
    continue
  fi
  # Skip branches checked out in any linked worktree.
  if git worktree list --porcelain | grep -q "^branch refs/heads/${branch}$"; then
    echo "  skip   ${branch} (checked out in a worktree)"
    skipped=$((skipped + 1))
    continue
  fi
  if [[ "${dry_run}" == true ]]; then
    echo "  would delete ${branch}"
  else
    echo "  delete ${branch}"
    git branch -d "${branch}"
  fi
  deleted=$((deleted + 1))
done < <(git branch --merged "${base}" | sed 's/^[*+ ]*//')

echo "Done. ${deleted} branch(es) processed, ${skipped} skipped."
