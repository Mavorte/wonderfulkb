# Agent Components Reference

Read this reference before changing agent configuration, prompts, or skills.

## Choose the owning file

| Change | Author it in |
|---|---|
| Agent-wide identity, routing, and behavior | `config.json`, `base.md`, `summary.md`, or `tags.md` |
| A conversational capability | `skills/<skill>/skill.json` and its referenced prompt files |
| A backoffice capability | `skills/<skill>/SKILL.md` |
| Tool implementation | `tools/<tool>/index.ts` or the shared library |

Keep prompts as authored Markdown files. Keep component configuration as JSON. Do not put a full prompt inline in `skill.json`, and do not create both conversational and backoffice formats in one skill directory.

## Make a focused change

1. Run `wful agents schema` and read the relevant schema first.
2. Start from the closest existing component; preserve its stable identifiers and file relationships.
3. Change the smallest coherent set of configuration and prompt files.
4. Add or remove tool and knowledge-base attachments in the owning skill, not in an unrelated global file.
5. Run local validation, inspect the diff, push, then run remote validation.

The schema is authoritative for fields and defaults. Prompts supply behavior, while JSON supplies structure and attachments; keep those responsibilities separate.
