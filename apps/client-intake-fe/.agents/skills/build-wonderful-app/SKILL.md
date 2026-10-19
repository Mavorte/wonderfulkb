---
name: build-wonderful-app
description: Build, test, review, and publish a git-backed Wonderful App and its managed resources.
---

# Build a Wonderful App

Treat this checkout as the source of truth. Use native Git for branches, commits, pulls, and pushes, and `wful` for Wonderful-aware CI and repository operations.

Read [references/actions.md](references/actions.md) before creating, inspecting, or rerunning CI workflows.
Read [references/codeowners.md](references/codeowners.md) before creating or changing CODEOWNERS, or when a pull request requires an owner review.

Keep app source under `app/` and preserve the existing managed function and table layout. Do not edit generated bundles or dependency caches. Run the repository's existing tests and type checks before pushing. After pushing, run `wful actions checks --watch --exit-status`; App pull-request checks are also shown in Pull Requests → PR detail → Checks.

## Local dependencies

`@wonderful/*` packages come from the environment's private registry at `https://<api-host>/api/npm/`, not from npmjs. On a developer's own computer, an `ERR_PNPM_FETCH_404` or a 404 from `registry.npmjs.org` for a `@wonderful/*` package means the computer is not set up yet, not that the package is missing. Any signed-in user can fix it once, without a token from Wonderful or a platform admin, with the API host of the `wful` profile that cloned the app (`wful apps clone` prints the exact command; with `--json`, it returns the command as `registry_login_command`):

```bash
npm login --auth-type=web --scope=@wonderful --registry=https://<api-host>/api/npm/
```

Then run `pnpm install` in `app/`.

## Call app Functions

App code calls a Function of this repository by its folder-qualified slug: `api.invokeFunction("<app-slug>/<path_slug>", { method, params })`, for example `api.invokeFunction("notes/notes-list")`. `<app-slug>` is the app's slug, normally the `slug` in `wonderful.json`. `<path_slug>` is the `path_slug` in `functions/<name>/config.json`. `wonderful.json` keys such as `function_gates` and `mcp.tools` use the folder name `<name>`; only the call is qualified.

A bare slug fails the app-token allowlist at runtime with a 403 `function not permitted`. The 403 does not say its cause, so check in this order:

1. The call uses `<app-slug>/<path_slug>`, not the bare slug.
2. The call's `method` matches the `method` in `config.json`. `invokeFunction` sends `POST` when you omit it.
3. The Function is in `functions/`, the deploy succeeded, and `wful apps resources-list --app <app-slug>` lists it. In a Preview, a Function that only the branch adds is allowed without a link, so skip this step for it.
4. The caller passes the Function's `function_gates` entry. A share-link visitor has only the roles of the app's anonymous audience.

Redeploying without a change does not fix it.

## Preview a branch before merging

Only a push to the deploy branch (usually `main`) activates a new live app version. A push to any other branch only builds it. Use a branch and a pull request for a change, and offer a Preview so the user can try it before the merge:

1. Create a branch without `/` in its name (for example `customer-search`); a push of `feature/x` is rejected. Commit, push, and open a pull request with `wful pr create`.
2. Run `wful apps preview-build <app-slug> --branch <branch> --json`. It returns the Preview id and its status (`building` while it builds) and prints no URL.
3. `preview-build` does not wait. Repeat `wful apps preview-inspect <app> --preview <id> --json` until `status` is `ready`, `pending_deployment_id` is absent, and `commit_sha` equals the pushed branch head (`git rev-parse HEAD`). Stop if `status` is `failed`, or if `status` is `ready` with `last_error` set and no `pending_deployment_id`: report `last_error`, then read the build log with `wful apps build-log --app <app> --deployment <id>` (`wful apps deployments --app <app>` lists each build's id and branch).
4. When the Preview serves the branch head, tell the user to click **Preview** on the pull request page.

A Preview uses the live secrets, global variables, and connections. A table set to `reuse` in `wonderful.json` `preview.tables` reads and writes the production rows, so check that policy before you test writes.

## MCP tools

Publish an MCP tool by exporting an existing app-owned HTTP Function. Do not add an MCP server, protocol handler, or second implementation to the repository.

1. Add an object `input_schema` and optional `output_schema` to `functions/<slug>/config.json`.
2. Add `{ "name": "domain.action", "function": "<slug>", "access": "read|write|destructive" }` under `mcp.tools` in `wonderful.json`.
3. Merge the change into the deploy branch. The active app version, Function code, contracts, and MCP tool catalog change together.

The referenced Function must live in this repository and have `kind: "http"`. Tool descriptions and schemas come from its config, so never duplicate them in `wonderful.json`.

## Service accounts

A Function whose `context.api` calls need a service account names it in `config.json` as `"service_account": "<name>"`, not by id. The name must be declared in `wonderful.json` `catalog.required_service_accounts`; a Catalog install of the app binds the account it provisioned under that name. A push naming an account that no Catalog install of this app provides is rejected. A push keeps the bindings it does not change, but cannot bind a Function to a named account it does not already run as (a new Function, a moved one, or one whose account an admin removed); only a Catalog install or upgrade that ships the binding does. A `config.json` that names no account leaves the Function's account as it is; change or remove it in the Function's settings.

## Function gates

Gate app-owned HTTP Functions in `wonderful.json`, next to `roles`: `"function_gates": {"<slug>": {"required_permissions": ["<key>"]}}`, or `{"allowed_roles": ["<role>"]}` (the legacy form). Each entry sets exactly one of the two, and only names from the `roles` catalog in `wonderful.json` (or the app's current roles when it has none). The key is the `functions/<slug>` folder name of a non-public `kind: "http"` Function. Without `function_gates`, gates stay as App Settings set them. With it, even `{}`, the repository owns every Function gate, so a Function you leave out is ungated: list every gate you want to keep. The gate applies to app members calling the Function from the app UI, the app API, and MCP tools. A call made with the app's own API or MCP credential has no member: `allowed_roles` does not apply to it and `required_permissions` rejects it, so use `required_permissions` when the Function must stay restricted there. Never put these keys in `config.json`.

## Assistant skills and Context Hub steps

An assistant skill the app ships is listed in `wonderful.json` as `"assistant_skills": ["<name>"]` and lives in `skills/<name>/`: a `SKILL.md` whose frontmatter `name` is `<name>`, plus any other files. A `skills/` folder that is not listed is not an assistant skill. A push to the deploy branch publishes new or changed skill content to every Wonderful Agent session of the tenant, so it needs a user with `prompts.agents:edit` and Wonderful Agent enabled; dropping the name from the list removes the skill. Skill names are tenant-wide, so a deploy fails when another skill already has the name. A skill that other installs of the app's Catalog plugin share changes only with a Catalog upgrade. Add a skill only when the user asked for one.

A Context Hub step is an app-owned HTTP `POST` Function plus an entry `{ "function": "<slug>", "stages": [...], "params_schema": {...} }` under `context_hub_steps` in `wonderful.json`. Code, route and service account stay in the Function's `config.json`.

## Table schema changes

Managed tables are declared in `tables/<name>.json`. If the repository has a `migrations/` directory, every table change must ship with a migration: edit the table JSON, run `wful apps migrate diff <snake_name>`, review the generated `migrations/<timestamp>_<name>.json`, and commit both. Pushes with table changes that no migration expresses are rejected. Never edit or delete an applied migration; add a new one that undoes it. Set `"backup": true` on a migration that can lose data so the platform snapshots the app before running it. Without `migrations/`, only additive table changes are accepted.

Never discard uncommitted work, rewrite history, merge, or publish unless the user explicitly requested it.
