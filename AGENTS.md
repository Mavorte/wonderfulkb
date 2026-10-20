# AGENTS.md

## Wonderful platform

This project is built on the Wonderful platform. Use the Wonderful SDK, the `wful` CLI, and the Wonderful skills for agents, apps, and deployments.

## Repository layout

- The root repository (`github.com/Mavorte/wonderfulkb`) tracks the full source, including every agent and app.
- Each agent and app (e.g. `apps/backoffice`) also has its own nested `.git` whose `origin` points to the Wonderful platform VCS (`vcs.sb.wonderful.ai`).

## AWS test environment — standing deployment authorization (2026-10-19)

Michal explicitly directs that completed WonderfulKB changes intended for the existing AWS test environment are installed and deployed there immediately as part of delivery. Routine dependency installation, packaging, in-place test deployment and bounded synthetic integration writes are authorized; do not insert a source-only/no-install/no-deploy hold or require another approval for these ordinary steps. Jackie owns operational deployment directly when the coding agent cannot complete it. Source completion is not deployed success: verify the actual deployed artifact/configuration and relevant live HTTP/database behavior, and report blockers honestly.

This authorization is for the existing AWS test environment, not production, unrelated cloud resources, public platform publication, destructive data operations or broad access changes. Inspect the current target and ownership, preserve existing configuration, retain a verified recovery artifact, use revision/concurrency guards, and keep synthetic writes scoped and accounted for. Existing history and failed/inconclusive evidence must not be overwritten or relabelled green. Do not replay ambiguous non-idempotent requests. Authentication failures and actual permission denials are real blockers; do not bypass them. For the current Case Client continuation preserve its approved bounded deployment/POST budget and existing fixtures.
