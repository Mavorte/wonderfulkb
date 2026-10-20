# Tool Authoring Reference

Read this reference before adding, changing, attaching, or debugging an authored tool.

## Choose the location

From an agent checkout, default to an agent-local tool:

```text
tools/<tool_slug>/index.ts
```

Use the agent's shared-library submodule only when the user explicitly asks for reusable behavior:

```text
shared_lib/tools/<tool_slug>/index.ts
```

If `shared_lib/` is absent and the user wants reusable behavior, run
`wful agents lib add` from the agent repository before creating the
tool. This attaches the latest commit from the Shared Library's default branch
unless the user requests an exact commit.

From a standalone shared-library checkout, reusable tools live at:

```text
tools/<tool_slug>/index.ts
```

Search the shared library before duplicating an existing tool. Tool names must start with a letter and otherwise contain only letters, digits, underscores, or hyphens; prefer lowercase names.

## Create a starter

For a new agent-local tool, run this from the agent root:

```bash
wful scaffold tool get_weather --description "Return the current weather for a city"
```

For a new reusable tool from an agent checkout, target the shared-library submodule explicitly:

```bash
wful scaffold tool get_weather --path shared_lib --description "Return the current weather for a city"
```

From a standalone shared-library checkout, use the first command from its root. The scaffolder creates `tools/<tool_slug>/index.ts`, refuses to overwrite an existing tool, and does not attach the tool to an agent. Replace the empty parameter schema and handler with the requested implementation before committing.

## Implement the tool

Default-export exactly one `w.tool()` value:

```ts
import { s, w } from "@wonderful/types/schema";

const params = s.object({
  city: s.string().describe("City to look up"),
  units: s.optional(s.enum("metric", "imperial")),
});

export default w.tool({
  name: "get_weather",
  description: "Return the current weather for a city",
  params,
  handler: async (_ctx, { city, units }) => {
    return { ok: true, city, units: units ?? "metric" };
  },
});
```

Rules:

- `name` is the runtime slug and must match the tool directory and attachment key.
- `params` must be an `s.object({...})` schema. Available builders include `string`, `number`, `boolean`, `any`, `object`, `array`, `enum`, `literal`, `optional`, and `union`.
- `handler` receives `(ctx, params)` and returns a JSON-serializable value.
- Keep the description explicit enough for the agent to decide when to call the tool.
- Add `.describe()` to every top-level parameter to explain how to fill it (format, allowed values, what not to pass) — these descriptions reach the runtime agent's tool schema, so document the parameter here instead of repeating instructions in agent prompts. Descriptions nested inside `object`/`array` fields are not propagated yet.
- Read credentials from configured secrets or environment wiring. Never hardcode credentials or tenant hosts.

### Call an LLM

Before adding a direct LLM call, create a Model Profile in Wonderful under
**Model Profiles → Profiles → Create profile**. Use its tenant profile UUID, or
an intentionally selected built-in static profile key. Never invent a profile
ID.

```ts
import { LangChainCore, ModelProfiles } from "@wonderful/types/langchain";

const model = new ModelProfiles.ChatModel({ profile: "<profile-uuid>" });
const response = await model.invoke([
  new LangChainCore.SystemMessage("Summarize the supplied order note."),
  new LangChainCore.HumanMessage(orderNote),
]);
```

Do not add model credentials, provider URLs, or raw model endpoints to tool
code. Model-specific APIs remain available for existing tools, but they will be
deprecated. Migrate them to `ModelProfiles.ChatModel` when changing their LLM
integration.

## Attach the tool

Implementing `index.ts` does not expose the tool. Attach it in the owning skill's `skill.json` through an object keyed by the same runtime name:

```json
{
  "name": "weather",
  "display_name": "Weather",
  "description": "Answer weather questions",
  "prompts": {
    "skill": "prompts/skill.md"
  },
  "tools": {
    "get_weather": {
      "type": "programmable",
      "config": {}
    }
  }
}
```

The `tools` value is a map, not an array. The built `w.tool()` manifest supplies the description and parameter contract, so do not duplicate generated `description` or `parameters` fields in `skill.json`. For a single-skill agent, attach the tool to that skill instead of adding an agent-level global tool.

For a shared-library tool, the attachment belongs in each consuming agent repository's `skill.json`; do not add agent skill configuration to the shared-library repository.

## Verify

From an agent root, run both validation tiers around the Git push:

```bash
wful validate
git push origin HEAD
wful validate --remote
```

In a standalone shared-library checkout, run `wful validate` and its existing tests or type-check command, then push so the server can build and validate the tool. When an agent pins that shared-library commit, validate the consuming agent remotely too.

If installed dependencies include TypeScript, use the repository's existing type-check command or `pnpm exec tsc --noEmit`. Do not use `npx tsc` to install an unrelated package. Commit source only; never commit generated bundles.
