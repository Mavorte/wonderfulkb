# Promotion Reference

Read this reference before promoting an agent between environments.

## Prepare the source

Promotion runs from an agent checkout on a workstation, never from a sandbox. Commit the intended source revision first; uncommitted files are never promoted. With `--from <profile>`, push and remotely validate the revision because `wful` fetches that environment's default variants. With `--local`, `wful` uses the current branch's committed `HEAD` without contacting a source environment.

Authenticate with both environments and select the intended workspace for each:

```bash
wful login --profile staging
wful login --profile prod
```

Initialize the agent's shared library when it is pinned:

```bash
git submodule update --init shared_lib
```

Before promoting a revision with exact `"{{global.NAME}}"` references in `config.json`, create a variable with the same name and a compatible type in the target workspace. Global Variables and their resolved values are not promoted through Git. Do not replace references with target literals to make validation pass.

## Stage the promotion

Run this from the agent root:

```bash
wful agents promote --from staging --env prod
```

To promote the current branch's committed `HEAD` instead, use:

```bash
wful agents promote --local --env prod
```

The command resolves the agent from the clone, fetches both environments, and stages the target-side merge branches. When shared libraries differ, it stages and opens the shared-library merge request first, re-pins the agent gitlink, then opens the agent merge request. The agent merge is gated on the library merge. If the agent does not yet exist in the target environment, `wful` forks it there first.

After the promoted revision is pushed, remotely validate it against the target environment:

```bash
wful --env prod validate --remote
```

This resolves target-workspace Global Variables and catches missing names, incompatible types, and invalid effective configuration before publish. Preserve the authored references when resolving promotion conflicts and during unrelated config edits.

Use `--no-mr` only when the user wants to open the staged merge requests manually. Use `--target-workspace <id>` when the target environment's workspace is not the intended destination. Use `--allow-unrelated-history` only for an explicitly approved one-time history link.

## Finish safely

Review the generated merge requests and their target-environment validation. Resolve behavioral conflicts deliberately; do not overwrite target configuration, prompts, tags, metrics, or tool behavior just to make a merge succeed. `wful agents promote` never merges the requests—merge the shared library first, then the agent, when review and checks allow it.
