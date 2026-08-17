Contributing to Synapic

- Overview
  This project is a Python-based daemon/SaaS-like tool for AI-powered image tagging in DAM workflows.

- Getting started
  1. Install dependencies: run `pip install -r requirements.txt` (or use pyproject.toml with a tool like Poetry).
  2. Run unit tests: `python -m pytest tests/ -q`.
  3. Run integration tests (requires DAM server): `RUN_INTEGRATION_TESTS=1 python tests/test_daminion_api.py`.

- Linting and formatting
  Use pre-commit or run: `ruff src tests` and `pytest`.

- Submitting changes
  Create a feature branch, implement changes, add tests, run tests, and open a PR.
  The repository auto-deletes head branches when a PR is merged, and `main` is
  protected against force-pushes and deletion.

- Branch cleanup
  Merged branches are pruned automatically on GitHub when a PR merges. For
  branches merged locally, run `./scripts/prune_merged_branches.sh` (or with
  `--dry-run` to preview) to delete local branches fully merged into the
  current branch. Branches checked out in a worktree and `main` are never
  touched. Optional alias: `git config --global alias.prune-branches
  '!bash scripts/prune_merged_branches.sh'`.

- Environment and secrets
  Do not commit secrets; use environment variables for server credentials in tests.
