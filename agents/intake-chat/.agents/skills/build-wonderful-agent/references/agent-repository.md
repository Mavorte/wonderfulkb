# Agent Repository Reference

Read this reference when changing agent structure, component JSON, validation, review, or promotion.

## Repository layout

```text
config.json
base.md
summary.md
tags.md
skills/<skill>/skill.json
skills/<skill>/prompts/skill.md
tools/<tool>/index.ts
tags/<tag>.json
metrics/<metric>.json
evals/scenarios/<scenario>.json
evals/batches/<batch>.json
kbs/<knowledge_base>/kb.json
shared_lib/                         # optional Shared Library pinned as a submodule
```

Keep `skills/`, `tools/`, `tags/`, `metrics/`, `evals/scenarios/`, `evals/batches/`, and `kbs/` present. Do not remove their `.gitkeep` files while a directory is otherwise empty.

## Create a new element

Use the repository-aware scaffolder instead of copying another element:

| Element | Command | Created path |
|---|---|---|
| Tool | `wful scaffold tool <slug>` | `tools/<slug>/index.ts` |
| Skill | `wful scaffold skill <slug>` | Mode-appropriate files under `skills/<slug>/` |
| Tag | `wful scaffold tag <slug>` | `tags/<slug>.json` |
| Scenario | `wful scaffold scenario <slug>` | `evals/scenarios/<slug>.json` |
| Batch | `wful scaffold batch <slug> --scenario <scenario_slug>` | `evals/batches/<slug>.json` |

Create referenced scenarios before creating a batch. The scaffolder refuses to overwrite an existing element and does not stage, commit, publish, or attach a tool. Run `wful scaffold <kind> --help` for metadata flags and examples, then replace any `TODO` placeholders in the created files.

## Current schemas

The scaffolder supplies the current starter shape for supported new elements. Run this from the agent root before a schema-sensitive manual change or when extending a starter beyond its generated fields:

```bash
wful agents schema
```

The command writes the platform's current JSON Schemas under `.wonderful/` and wires them into the editor. Read only the schema relevant to the file being changed. Do not guess fields or copy an old full `config.json` over the seeded configuration.

Common paths are:

| Authored file | Schema or source |
|---|---|
| `config.json` | `.wonderful/agent-config-schema.json` |
| `skills/*/skill.json` | `.wonderful/skill-config-schema.json` |
| `tags/*.json` | `.wonderful/tag-config-schema.json` |
| `metrics/*.json` | `.wonderful/metric-config-schema.json` |
| `evals/scenarios/*.json` | The scenario schema written by `wful agents schema` |
| `evals/batches/*.json` | The batch schema written by `wful agents schema` |

## Typed Global Variable references in config.json

Use an exact quoted reference when a config value must differ by environment while the repository stays identical:

```json
{
  "behavior": {
    "guardrails": {
      "pii": {
        "policies": [
          {
            "name": "Credit-Card Numbers",
            "instruction": "",
            "enabled": "{{global.ENABLE_CREDIT_CARD}}",
            "source": "built_in",
            "built_in_key": "credit_card"
          }
        ]
      }
    }
  }
}
```

The reference must occupy the complete JSON string. Never write an unquoted placeholder or `{ "$global": "ENABLE_CREDIT_CARD" }`. The workspace supplies the referenced value's native Boolean, number, string, enum, object, or array type.

Keep `profile.name`, `profile.display_name`, and `profile.mode` as literals. They are mirrored into publish-time identity metadata and cannot be Global Variable references.

Preserve exact references during unrelated edits. Do not resolve them locally and commit the resulting literals. Create a matching, type-compatible Global Variable separately in every target workspace, push the repository revision, and run `wful validate --remote` in that environment.

For PII configuration:

- There is no `pii.enabled` master switch. PII is active when at least one effective policy is enabled.
- To toggle all policies together, reference the same Boolean variable from every policy's `enabled` field.
- Deterministic PII scrubbing always runs when PII is active.
- PCI mode still forces its required built-in policies. A false Global Variable cannot disable them or disable PCI mode.

## Minimal skill

Non-backoffice agents use `skills/<name>/skill.json` plus authored prompt files:

```json
{
  "name": "booking",
  "display_name": "Booking",
  "description": "Help customers make and change bookings",
  "tools": {},
  "prompts": {
    "skill": "prompts/skill.md"
  }
}
```

Create the referenced `skills/booking/prompts/skill.md` too:

```md
# Booking

Help the customer make or change a booking. Ask only for information needed for the next step.
```

Backoffice agent skills use `skills/<name>/SKILL.md` instead:

```md
---
name: booking
description: Process booking requests and report the result.
---

# Booking

Process the requested booking task and return a concise result.
```

Do not create both skill formats in the same directory.

## Validation and review

```bash
wful validate
git status --short
git diff --check
git add <intended-paths>
git commit -m "<message>"
git push origin HEAD
wful validate --remote
wful pr create
```

Local validation checks the working tree. Remote validation checks the pushed commit and is authoritative for environment-backed references and server-side tool builds.

## Shared-library changes

An agent repository may not use the Shared Library. Add or remove it only when
the user asks:

```bash
wful agents lib add
wful agents lib remove
```

Add uses the latest commit from the Shared Library's default branch. Pass
`--commit <full-commit-sha>` for an exact version. Both commands change only the
local working tree, leave files unstaged, and run local validation. Removal does
not change the workspace Shared Library or other agents. If validation reports
shared tool or configuration references after removal, keep the changes and
clean up the reported agent files before committing. Validation does not scan
tool source code for imports.

Commit and push shared-library changes inside `shared_lib/` first. Then return to the agent root, update the gitlink, validate, and commit the agent change. The library commit must be reachable from the Shared Library's default branch before the agent merge can complete.

For promotion between configured environments:

```bash
wful agents promote --from staging --env production
```

Promotion stages the shared library before the agent and opens review requests. It does not merge them automatically.
