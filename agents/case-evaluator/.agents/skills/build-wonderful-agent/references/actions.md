# Wonderful Actions CI

Wonderful Actions reads GitHub-compatible workflow files from `.wonderful/actions/workflows/*.yml` or `.yaml` at the immutable pushed commit.

## Author a workflow

```yaml
name: Repository checks
on: [push, pull_request, workflow_dispatch]

jobs:
  test:
    runs-on: wonderful-sandbox
    steps:
      - name: Install dependencies
        run: pnpm install --frozen-lockfile
      - name: Run tests
        run: pnpm test
```

Use `runs-on: wonderful-evals` with `wonderful/agent-evals@v1` for Agent Studio eval batches. Use `runs-on: wonderful-sandbox` with `run` commands for repository tests. A job uses one backend; do not mix eval and sandbox steps in one job. Use `runs-on: <container name>` to run a sandbox job inside a workspace Wonderful Container that is enabled for CI actions.

Workflow, job, and sandbox-step `env` maps accept literal values and exact `${{ vars.NAME }}` or `${{ secrets.NAME }}` references. Secret references resolve for `push`, `pull_request`, and `workflow_dispatch` runs. Never commit secret values. Upload files from a sandbox job with `wonderful/upload-artifact@v1`; paths are repository-relative and may not use wildcards, absolute paths, or `..`.

## Inspect and rerun CI

After pushing, use the Wonderful CLI instead of polling API responses manually:

```bash
wful actions checks --watch --exit-status
wful actions list --commit HEAD
wful actions view <run-id>
wful actions watch <run-id> --exit-status
wful actions rerun <run-id>
wful actions rerun --job <job-id>
```

`wful ci` is an alias for `wful actions`. The commands intentionally mirror the useful parts of `gh run` and `gh pr checks` while using Wonderful repository identity and authentication.

For a Wonderful merge request:

```bash
wful pr create
wful pr checks <number> --watch --exit-status
wful pr view <number>
```

Do not merge while required checks are queued, running, failed, cancelled, or unavailable. Fix the source, push it, and watch the new immutable run. Rerun only when retrying the same commit is appropriate.

App repositories expose CI in the App's Pull Requests page: open the PR detail and use its Checks view. Function and Shared Library PRs expose the same checks in their PR detail views.
