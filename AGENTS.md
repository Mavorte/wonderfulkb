# AGENTS.md

## Wonderful platform

This project is built on the Wonderful platform. Use the Wonderful SDK, the `wful` CLI, and the Wonderful skills for agents, apps, and deployments.

## Repository layout

- The root repository (`github.com/Mavorte/wonderfulkb`) tracks the full source, including every agent and app.
- Each agent and app (e.g. `apps/backoffice`) also has its own nested `.git` whose `origin` points to the Wonderful platform VCS (`vcs.sb.wonderful.ai`). Deploy to the platform from inside that directory, using its own git configuration.
- A change to an agent or app goes to both places: commit and push in the nested repo to deploy, and commit it in the root repo to keep the full source in sync.

## Branches and worktrees

- Make every change on a feature branch, never directly on `main`. Use dashes, not slashes, in branch names (e.g. `feat-case-list`).
- For larger tasks, work in a separate git worktree so `main` and other work stay untouched.

## Merge requests on Wonderful platform

Always merge with `--delete-source` (`wful pr merge <number> --delete-source`) so merged branches do not pile up on the remote.
