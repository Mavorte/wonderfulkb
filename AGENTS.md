# AGENTS.md

## Wonderful platform

This project is built on the Wonderful platform. Use the Wonderful SDK, the `wful` CLI, and the Wonderful skills for agents, apps, and deployments.

## Repository layout

- The root repository (`github.com/Mavorte/wonderfulkb`) tracks the full source, including every agent and app.
- Each agent and app (e.g. `apps/backoffice`) also has its own nested `.git` whose `origin` points to the Wonderful platform VCS (`vcs.sb.wonderful.ai`). Deploy to the platform from inside that directory, using its own git configuration.
- A change to an agent or app goes to both places: commit and push in the nested repo to deploy, and commit it in the root repo to keep the full source in sync.

## Branches and worktrees

- Coding and planning agents must not create, switch, merge, rebase, commit, push, delete branches, or create/remove worktrees. Git lifecycle is owned exclusively by the host operator (Jackie), following Michal's explicit direction.
- Agents share this checkout and may run in parallel. Work on the branch already checked out by the host; never switch branches to satisfy a planning skill or a generic feature-branch convention.
- The root checkout uses `main` unless Michal explicitly requests a different branch through the host. Any required branch/worktree operation must be reported to the host, not executed by a task agent.
- These ownership rules also apply to the nested Wonderful repositories: agents prepare source and verification only; host-managed publication retains its separate approval requirements.

## AWS test environment — standing deployment authorization (2026-10-19)

Michal explicitly directs that completed WonderfulKB changes intended for the existing AWS test environment are installed and deployed there immediately as part of delivery. Routine dependency installation, packaging, in-place test deployment and bounded synthetic integration writes are authorized; do not insert a source-only/no-install/no-deploy hold or require another approval for these ordinary steps. Jackie owns operational deployment directly when the coding agent cannot complete it. Source completion is not deployed success: verify the actual deployed artifact/configuration and relevant live HTTP/database behavior, and report blockers honestly.

This authorization is for the existing AWS test environment, not production, unrelated cloud resources, public platform publication, destructive data operations or broad access changes. Inspect the current target and ownership, preserve existing configuration, retain a verified recovery artifact, use revision/concurrency guards, and keep synthetic writes scoped and accounted for. Existing history and failed/inconclusive evidence must not be overwritten or relabelled green. Do not replay ambiguous non-idempotent requests. Authentication failures and actual permission denials are real blockers; do not bypass them. For the current Case Client continuation preserve its approved bounded deployment/POST budget and existing fixtures.

## Merge requests on Wonderful platform

Always merge with `--delete-source` (`wful pr merge <number> --delete-source`) so merged branches do not pile up on the remote.
