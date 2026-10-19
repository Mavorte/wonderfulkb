# AGENTS.md for Template Forks

This file is for developers (and coding assistants) working in a fork of this template.
Use it as the implementation contract for a Wonderful App bundle.

## Layout Gotcha — Read This First

`Box`'s `direction` prop **defaults to `"row"`**, and the prop is optional, so
TypeScript accepts a bare `<Box gap={4}>` that you meant as a vertical stack.
It renders horizontally: cards shrink to content width, tiles become slivers,
and the screen spills off the right edge. It looks like the grid is broken, and
rewriting `Row`/`Col` will not help.

- Vertical stack → **`<Stack gap={n}>`**
- Horizontal group → **`<Box direction="row" gap={n}>`**
- Always pass `direction` when you use `Box`.

If a screen looks like the grid broke, check this before touching any grid code:
`rg '<Box(?![^>]*direction)' src/`

## JavaScript / TypeScript Conventions

Non-negotiable, and identical to the platform monorepo's `js-standards`:

- **Write functionally.** Every logical component is obtained by calling a
  function — never export a bare instance or a class for the caller to `new`.
- **Function names start with a verb**, and most are `get*` or `create*`:
  `create*` always constructs something new, `get*` returns an existing or
  cached thing. **Never `build*`** — use `create*`. A cached `create*` is
  wrapped by a `get*`; never cache inside a `create*`.
- **Camel-case identifiers**: `lowerCamelCase` variables and functions,
  `UpperCamelCase` classes and types, `SCREAMING_SNAKE_CASE` module constants.
  Never `snake_case`.
- **One component per file, named after it, `export default`.** The file may
  also export minor related types/helpers as named exports. A function's file is
  lowercase (`createTicket.ts`); a **class's** file starts with a capital
  (`TicketStore.ts`), like a React component file.
- **A big file becomes a folder of the same name**, exposed through an
  `index.ts` that `export default`s the same component, so import sites don't
  change. The internals become sibling files inside that folder and stay
  private to it; if one turns out to be shared, it moves out rather than being
  exposed. This nests.
- **Barrels for libraries** and library-like folders (`utils/`, `common/`,
  `lib/`) — never a barrel on a top-level `src/` folder. Import through the
  descendant.
- **A class is allowed where memory warrants it** (large structures, prototype
  sharing) but is never the exported surface: expose it through a `create*`
  factory — `createSomething/index.ts` + `Something.ts`, with
  `createSomething = (...args) => new Something(...args)`.

React components keep their framework naming: a component is a noun
(`OpenTicketsWidget`), a hook is `use*`. The verb rule governs plain functions.

- **Scripts are TypeScript**, run as natively as possible: bare `node
  script.ts` first (no loader, no dependency), `tsx` only when the script needs
  path aliases or non-erasable syntax. Don't add new `.mjs`/`.js` scripts.
  Native running requires erasable-only TS — no `enum`, `namespace`,
  constructor parameter properties or `import =`; use `import type` for
  type-only imports and a `const` object plus a union type instead of an enum.

## Exposing a Widget

To let another app embed part of this app, export that part by
name from `src/index.ts` and declare it in `wonderful.json`:

```json
"widgets": [
  { "key": "open_tickets", "name": "Open tickets", "export": "OpenTicketsWidget", "size": "ms" }
]
```

The `default` export stays the app itself and can never be a widget. `size` is
a canvas-cell preset — `"s"` (1x1), `"mw"` (2x1), `"ms"` (2x2, the default) or
`"l"` (3x2) — or `{ "width": 640, "height": 400 }`; a widget
component receives an optional `params` object from its host. Embed another
app's widget with `<AppWidget app="<slug>" widget="<key>" />` from
`@wonderful/app-sdk` — it renders nothing in the local runner, which serves
only this app.

Build the widget itself from the `wonderful-app-widgets` skill: it sets the
sizes, states and chart rules, and ships a widget kit to copy into
`src/widgets/kit/`. The host draws the card, so the widget's root never paints
its own background, border or shadow.

## What to Keep Intact

- Keep `src/index.ts` as a default export entry point for your app component.
- Keep the bundle contract: `pnpm build` outputs `dist/app.js` (and optional `dist/style.css`).
- Keep packaging contract: `pnpm package` must include build files plus `manifest.json`.
- Keep the source-in-bundle contract: `pnpm package` ships a snapshot of the
  app's source under `source/` inside the zip. The controller stores it inside
  `bundle.zip` for `controller-cli apps download --extract` round-trips, but
  never serves it to the deployed app. To rebuild a fresh source checkout from
  a deployed app: `controller-cli apps download --app <slug> --extract <dir>`.
  Set `BUNDLE_INCLUDE_SOURCE=false` only if you intentionally need a
  source-free bundle (rare; loses the ability to round-trip edits).

## First Steps After You Fork

1. Dependencies are already declared in `package.json`. Agent Builder prepares
   `node_modules`; outside Agent Builder, run this only when dependencies are
   missing (on your own computer, first set up the registry as described in
   "Local development outside a Wonderful sandbox" below):

```bash
pnpm install
```

Do not run `pnpm add @wonderful/app-sdk`: it is a host-provided runtime module,
not a published package. Keep `@wonderful/ui-base` at the version already pinned
in `package.json`; it must match the UI ABI provided by the Wonderful app host.

GenUI is optional and is not declared in the base template. Only when the app
imports `GenUISurface` (or another export from `@wonderful/genui-react`), add the
pinned package as a dev dependency:

```bash
pnpm add -D @wonderful/genui-react@0.2.0
```

This updates the opted-in app's `package.json` and lockfile so `tsc --noEmit`
can resolve the package's types. Keep `@wonderful/genui-react` in Vite's
`external` list: the Wonderful host supplies the runtime module, so it is not
included in the app bundle.

2. Build your app UI in `src/App.tsx` (or split into `src/components/*`).
3. Use runner mode when building features that call Wonderful APIs.

Agent Builder configures the authenticated `@wonderful` registry for its
environment. Do not add an absolute `@wonderful:registry` entry to the project
`.npmrc`; it can override the authenticated environment mapping.

### Local development outside a Wonderful sandbox

`@wonderful/*` packages come from the environment's private registry at `https://<api-host>/api/npm/`, not from npmjs. On a developer's own computer, an `ERR_PNPM_FETCH_404` or a 404 from `registry.npmjs.org` for a `@wonderful/*` package means the computer is not set up yet, not that the package is missing. Any signed-in user can fix it once, without a token from Wonderful or a platform admin, with the API host of the `wful` profile that cloned the app (`wful apps clone` prints the exact command; with `--json`, it returns the command as `registry_login_command`):

```bash
npm login --auth-type=web --scope=@wonderful --registry=https://<api-host>/api/npm/
```

Then run `pnpm install` in `app/`.

## Styling

This template uses plain CSS.

- Keep `src/index.ts` export-only (no CSS imports).
- Import `src/style.css` from `src/App.tsx` (or your top-level app component).
- Write styles in `src/style.css` using standard CSS. The file is bundled into `dist/style.css` on build.

## Accessing Wonderful APIs from the App

Use `useWonderful()` from `@wonderful/app-sdk`. Do not put API keys or controller base URLs in browser code.

```tsx
import { useEffect, useRef, useState } from "react";
import { useWonderful } from "@wonderful/app-sdk";

type ApiEnvelope<T> = {
  data: T;
  status?: string;
};

type AgentSummary = {
  id: string;
  display_name: string;
};

export default function AgentsList() {
  const { api } = useWonderful();
  const apiRef = useRef(api);
  apiRef.current = api;
  const [agents, setAgents] = useState<AgentSummary[]>([]);

  useEffect(() => {
    const load = async () => {
      const response = await apiRef.current.get<ApiEnvelope<AgentSummary[]>>(
        "/api/v3/agents?page=1&limit=10",
      );
      setAgents(response.data);
    };
    void load();
  }, []);

  return (
    <div>
      <pre>{JSON.stringify(agents, null, 2)}</pre>
    </div>
  );
}
```

### API Path Rules

- `api.get("/something")` -> `/api/v1/something`
- `api.get("/api/v3/agents")` -> `/api/v3/agents` (keeps explicit `/api/*`)

Use explicit `/api/v3/agents` paths for agent integrations. These routes require Wonderful Agent provisioning. Creating an agent uses `POST /api/v3/agents` with `display_name` and the fields required for its mode.

## Importing UI from `@wonderful/ui-base`

Use root imports from `@wonderful/ui-base` (no deep imports).

```tsx
import { Button, InputText, Stack, Text } from "@wonderful/ui-base";
import { useState } from "react";

export function CreateForm() {
  const [name, setName] = useState("");

  return (
    <Stack gap={3}>
      <Text variant="heading-3">Create item</Text>
      <InputText
        label="Name"
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      <Button
        isDisabled={!name.trim()}
        onClick={() => {
          // submit action
        }}
      >
        Save
      </Button>
    </Stack>
  );
}
```

### UI Import Rules

- Prefer `@wonderful/ui-base` components over custom primitives.
- Import types as `import type { ... } from "@wonderful/ui-base"` when needed.
- Avoid deep imports like `@wonderful/ui-base/dist/...`.

## Local Development Modes

- `pnpm dev`: static UI iteration.
- `pnpm runner`: preferred for SDK context + API integration testing.

Runner reads `WONDERFUL_API_KEY` server-side and proxies app API calls through `/proxy/*`.

### Required Local Runner Compatibility

Keep these behaviors when editing template infrastructure:

- Load `@wonderful/ui-base/style.css` in local entrypoints:
  - `dev/main.tsx`
  - `runner/main.tsx`
- Do not import `@wonderful/ui-base/style.css` from `src/index.ts` (bundle entry).
- Do not import `src/style.css` from `src/index.ts` (bundle entry).
- In `runner/server.mjs`, preserve proxy decoding safeguards:
  - remove `accept-encoding` before proxying upstream requests
  - remove `content-encoding` when forwarding upstream responses
- Keep `@wonderful/app-sdk` aliasing to `runner/sdk-shim.ts` for `dev` and `runner` modes in `vite.config.ts`.

## Uploading to Wonderful

App upload is currently manual in the Wonderful UI.

1. `pnpm build && pnpm package`
2. Open your app in Wonderful UI
3. Upload the zip from `dist/` in the **Versions** page
4. Activate the uploaded version

Do not rely on API-key upload flow for app bundle publishing.

## Custom Tables API

Use `api` from `useWonderful()` to read and write custom tables.

```ts
// Create a table
await api.post("custom-tables", {
  name: "my_table",
  description: "...",
  columns: [
    { name: "title",  type: "string", required: true },
    { name: "amount", type: "number", required: true },
  ],
});

// Insert a row
await api.post("custom-tables/my_table/rows", {
  data: { title: "Foo", amount: 1000 },
});

// Fetch rows — pages are 1-indexed
const res = await api.get<{
  data: Array<{ id: string; data: Record<string, unknown> }>;
  pagination: { total_rows: number; total_pages: number; page: number; limit: number };
}>("custom-tables/my_table/rows?page=1&limit=20");

// Update a row
await api.put(`custom-tables/my_table/rows/${id}`, { data: { amount: 2000 } });

// Delete a row
await api.del(`custom-tables/my_table/rows/${id}`);
```

**Error behaviour:** When a table does not exist, the API returns **500**, not 404. Do not rely on 404 detection.

## Preventing Infinite Fetch Loops with `useWonderful()`

The `api` object from `useWonderful()` is recreated on every render. Using it directly in `useCallback` or `useEffect` deps causes an infinite loop. Store it in a ref:

```ts
const { api } = useWonderful();
const apiRef = useRef(api);
apiRef.current = api;

const fetchData = useCallback(async () => {
  const res = await apiRef.current.get("...");
  // ...
}, []); // empty deps — stable reference via ref

useEffect(() => { fetchData(); }, [fetchData]);
```

## Platform Design Tokens

The Wonderful platform ships a design token system (from `@wonderful/theme`, delivered via `@wonderful/ui-base`). Always use these tokens instead of hardcoded hex values so your app stays visually consistent with the platform and picks up future theme changes. The host drives dark mode with the **`data-theme-mode="dark"` attribute** (its values inherit into your app), so tokens flip automatically — never key off a `.dark` class or hardcode per-mode colors.

### Semantic tokens (prefer these)

Use the semantic tokens by role; they map onto the primitives below and flip with the mode. Available as CSS vars (`var(--card)`) and, if your build includes the ui-base utilities, as classes (`bg-card`, `text-foreground`, `border-border`, `bg-danger`, …):

| Role | Tokens |
|---|---|
| Surfaces | `--background`, `--background-secondary`, `--elevated` |
| Text | `--foreground` |
| Cards | `--card`, `--card-foreground`, `--card-secondary` |
| Form fields | `--input`, `--input-foreground`, `--input-border` |
| Borders | `--border`, `--border-subtle`, `--border-strong`, `--card-border` |
| Intent | `--primary`, `--secondary`, `--success`, `--warning`, `--danger`, `--accent` — each with a `-foreground` |

The raw primitives below still exist and back the semantic tokens — prefer the semantic ones.

### Surfaces & Borders

| Token | Light value | Dark value | Use for |
|---|---|---|---|
| `--surface-00` | `#ffffff` | `#181818` | Card / panel background |
| `--neutral-00` | `#fafafa` | `#080808` | Secondary surface, input background |
| `--neutral-100` | `#f5f5f5` | `#1e1e1e` | Page background |
| `--neutral-200` | `#f1f1f1` | `#252525` | Subtle tint |
| `--neutral-300` | `#e5e5e5` | `#2e2e2e` | Border, divider |
| `--neutral-400` | `#dbdbdb` | `#383838` | Strong border |
| `--neutral-500` | `#dddddd` | `#484848` | Disabled border |

### Text

| Token | Light value | Dark value | Use for |
|---|---|---|---|
| `--foreground-100` | `#141414` | `#f5f5f5` | Primary text |
| `--neutral-800` | `#393939` | `#e0e0e0` | Strong secondary text |
| `--neutral-700` | `#777777` | `#b0b0b0` | Secondary / label text |
| `--neutral-600` | `#a9a9a9` | `#9e9e9e` | Placeholder / muted text |

### Semantic Colors (static — same in light and dark)

Each semantic color comes in three strengths:

| Name | Full (`-100`) | Tint bg (`-5`) | Border (`-30`) |
|---|---|---|---|
| Blue | `#2399fa` | `#2399fa0d` | `#2399fa4d` |
| Green | `#03a97e` | `#03a97e0d` | `#03a97e4d` |
| Amber | `#faad14` | `#faad140d` | `#faad144d` |
| Red | `#ff3f3f` | `#ff3f3f0d` | `#ff3f3f4d` |
| Purple | `#ba98ff` | `#ba98ff0d` | `#ba98ff4d` |
| Orange | `#ffa75a` | — | — |

CSS variables: `--color-blue-100`, `--color-blue-5`, `--color-blue-30` (same pattern for each color).

**Typical badge pattern:**
```css
.badge-success {
  color:      var(--color-green-100);
  background: var(--color-green-5);
  border:     1px solid var(--color-green-30);
}
```

**Chart colors** — use the `-100` values: blue `#2399fa`, green `#03a97e`, amber `#faad14`, red `#ff3f3f`, purple `#ba98ff`, orange `#ffa75a`.

### How to use tokens in your app

Declare an alias layer on your root element so tokens resolve inside the Shadow DOM, then reference the aliases throughout your CSS:

```css
.app-root {
  /* Surfaces */
  --app-bg:       var(--neutral-100,  #f5f5f5);
  --app-surface:  var(--surface-00,   #ffffff);
  --app-surface2: var(--neutral-00,   #fafafa);
  --app-border:   var(--neutral-300,  #e5e5e5);

  /* Text */
  --app-text:     var(--foreground-100, #141414);
  --app-text-2:   var(--neutral-700,    #777777);
  --app-text-3:   var(--neutral-600,    #a9a9a9);

  /* Semantic */
  --app-blue:     var(--color-blue-100,  #2399fa);
  --app-blue-lt:  var(--color-blue-5,    #2399fa0d);
  --app-blue-bd:  var(--color-blue-30,   #2399fa4d);
  --app-green:    var(--color-green-100, #03a97e);
  --app-green-lt: var(--color-green-5,   #03a97e0d);
  --app-green-bd: var(--color-green-30,  #03a97e4d);
  --app-amber:    var(--color-amber-100, #faad14);
  --app-amber-lt: var(--color-amber-5,   #faad140d);
  --app-amber-bd: var(--color-amber-30,  #faad144d);
  --app-red:      var(--color-red-100,   #ff3f3f);
  --app-red-lt:   var(--color-red-5,     #ff3f3f0d);
  --app-red-bd:   var(--color-red-30,    #ff3f3f4d);
}
```

The hardcoded fallbacks ensure correct rendering in local `pnpm dev` / `pnpm runner` before the platform stylesheet loads. Always use a unique prefix (e.g. `--app-`, `--myapp-`) to avoid collisions with platform-level variables.

## Styling in Shadow DOM

Apps are embedded inside a Shadow DOM in the Wonderful UI. This affects CSS in two important ways:

### 1. Define CSS variables on your root element, not `:root`

CSS custom properties declared in `document.head` stylesheets do not reliably reach inside the shadow root. Re-declare all variables on the app's top-level element so they resolve for all descendants:

```css
.app-root {
  --myapp-bg: #F4F5F7;
  --myapp-text: #111827;
  --myapp-border: #E5E7EB;
  /* ... */
  background: var(--myapp-bg);
  color: var(--myapp-text);
  font-family: 'Inter', sans-serif;
  font-size: 14px;
}
```

### 2. Use a unique CSS variable prefix

The platform loads Tailwind v4 which defines common names like `--green`, `--blue`, `--red`, `--amber` as CSS variables. Using the same names will cause collisions. Always namespace your variables (e.g. `--myapp-green`, `--myapp-blue`).

### 3. Move `body` styles to your root element

`body {}` rules do not apply inside the shadow root. Any font, color, or background set on `body` must be moved to `.app-root` (or equivalent).

## Required Validation Before Handoff

Every implementation must run and pass:

```bash
pnpm install
pnpm build
pnpm build:runner
```

When handing work off to another agent, include:

- exact files changed
- short implementation summary
- results of the three required commands above
