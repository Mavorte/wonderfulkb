---
name: build-wonderful-agent
description: Build, edit, validate, review, and promote a Wonderful Agent Studio agent from its Git repository. Use when working with config, prompts, skills, tools, tags, metrics, evals, knowledge-base pointers, or the shared library from an agent checkout.
---

# Build a Wonderful Agent

Treat the current checkout as the source of truth. Use `wful` for platform operations and native Git for branches, commits, pulls, and pushes.

## wful availability

`wful` is the Wonderful CLI.

- If an attempted `wful` command indicates that the executable is missing or unavailable, stop and ask the user to install it using the instructions from their Wonderful environment. Do not invent an environment URL, download an unofficial binary, or ask the user to paste credentials into chat.
- If the attempted command reports an authentication or workspace problem, ask the user to complete `wful login` or select the intended profile or workspace. Never expose or persist credentials yourself.
- This repository already contains the `build-wonderful-agent` skill under `.agents/skills` and `.claude/skills`; no machine-level installation is required for this skill. `wful repo sync-skills` refreshes these committed copies.
- The optional general `wful` skill teaches Claude Code and Codex about platform-wide CLI workflows. With the user's approval, install or refresh it with `wful setup skill`; use `--claude` or `--codex` to target one coding agent explicitly.

## Workflow

1. Run `git status --short`, inspect the current branch, and preserve existing work.
2. Read [references/agent-repository.md](references/agent-repository.md) before changing repository structure or component JSON.
3. Read [references/tool-authoring.md](references/tool-authoring.md) before creating or editing a tool.
4. Read [references/agent-components.md](references/agent-components.md) before changing agent configuration, prompts, or skills.
5. Read [references/evaluations.md](references/evaluations.md) before authoring or running an evaluation.
6. Read [references/knowledge-and-rag.md](references/knowledge-and-rag.md) before creating or attaching a knowledge base.
7. Read [references/metrics-and-tags.md](references/metrics-and-tags.md) before changing metrics or tags.
8. Read [references/promotion.md](references/promotion.md) before promoting an agent between environments.
9. Read [references/actions.md](references/actions.md) before creating, inspecting, or rerunning Wonderful Actions CI.
10. Read [references/codeowners.md](references/codeowners.md) before creating or changing CODEOWNERS, or when a pull request requires an owner review.
11. For a new tool, skill, tag, scenario, or batch, run the matching `wful scaffold` command before editing. Author metrics and knowledge-base pointers manually using their references.
12. Edit authored source only. Do not edit `dist/`, downloaded schemas, dependency caches, or generated bundles.
13. Run `wful validate` from the agent root.
14. Review and commit only the intended files with native Git, then push the branch.
15. Run `wful validate --remote` after pushing. Use `wful pr create` when the change needs review, then `wful pr checks <number> --watch --exit-status` when CI is configured.

For cross-environment delivery, use `wful agents promote --from <source-environment> --env <target-environment>`. It stages the shared library before the agent and opens merge requests; it never merges them.

## Guardrails

- Default new tools to `tools/<tool>/index.ts` in the agent repository. Use `shared_lib/tools/<tool>/index.ts` only when the user explicitly wants reusable behavior.
- The Shared Library is optional. If reusable behavior is requested and `shared_lib/` is absent, follow [references/agent-repository.md](references/agent-repository.md) to add it before editing shared code.
- Author repository components as files. `wful scaffold` creates those local files; it is not a tenant-catalog CRUD workflow. Do not use tenant-catalog skill or tool CRUD commands for repository-owned definitions.
- Keep required placeholder directories and their `.gitkeep` files.
- Never discard uncommitted work, rewrite history, merge, or publish unless the user explicitly requested it.
- Run `wful repo sync-skills --check` to check whether this Wonderful-managed skill is current. Use `wful repo sync-skills` to update it explicitly.
