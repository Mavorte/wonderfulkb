// Build script for a Wonderful functions repo. Discovers every function folder
// (a directory containing a config.json) and bundles its index.ts entrypoint
// into dist/<folder>/index.js with esbuild. Run by the sandbox build via
// `pnpm build` after `pnpm install`, so relative cross-function imports,
// shared_lib, and npm dependencies all resolve. The controller commits the
// produced dist/ artifacts and ships them to the runner.
import { build } from "esbuild";
import { readdirSync, existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const IGNORED = new Set(["node_modules", "dist", ".git"]);

let parseJavaScript;
let analyzeJavaScriptScopes;
let rewritePattern;

const unicodeRegexBuildDependencies = [
  "wonderful-internal-acorn",
  "wonderful-internal-eslint-scope",
  "wonderful-internal-regexpu-core",
];

const unicodeRegexTransformerAvailable = hasBuildDependencies(unicodeRegexBuildDependencies);
const emitSourceMaps = process.env.WONDERFUL_EMIT_SOURCE_MAPS === "true";

function findFunctionFolders(dir) {
  const folders = [];
  if (existsSync(join(dir, "config.json")) && existsSync(join(dir, "index.ts"))) {
    folders.push(dir === "." ? "" : dir);
  }
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory() || IGNORED.has(entry.name)) continue;
    folders.push(...findFunctionFolders(join(dir, entry.name)));
  }
  return folders;
}

// WONDERFUL_BUILD_FOLDER scopes the build to a single function folder ("." = the
// repo-root function) so each function bundles against its own resolved
// dependencies. Unset (e.g. a local `pnpm build`) falls back to building every
// folder.

function resolveTargetFolders() {
  const batch = process.env.WONDERFUL_BUILD_FOLDERS;
  if (batch) {
    let folders;
    try {
      folders = JSON.parse(batch);
    } catch (error) {
      throw new Error(`invalid WONDERFUL_BUILD_FOLDERS: ${error.message}`);
    }
    if (!Array.isArray(folders) || folders.some((folder) => typeof folder !== "string")) {
      throw new Error("WONDERFUL_BUILD_FOLDERS must be a JSON string array");
    }
    return folders.map((folder) => (folder === "." ? "" : folder));
  }
  const target = process.env.WONDERFUL_BUILD_FOLDER;
  if (!target) return findFunctionFolders(".");
  const folder = target === "." ? "" : target;
  const dir = folder === "" ? "." : folder;
  if (!existsSync(join(dir, "config.json")) || !existsSync(join(dir, "index.ts"))) {
    console.error(`build target ${target} is not a function folder`);
    process.exit(1);
  }
  return [folder];
}

const folders = resolveTargetFolders();

if (folders.length === 0) {
  console.log("no function folders found; nothing to build");
  process.exit(0);
}

// The runner eval's the bundle as a classic script (no `module`/`require`) and
// calls a top-level `userFunction`/`main`. With an IIFE bundle those entry
// declarations are scoped inside the wrapper, and esbuild's globalName only
// re-exposes *exported* bindings — the default template's bare
// `async function userFunction(...)` (no export) would be lost. Append a
// typeof-guarded globalThis assignment to each entry's own source so the
// declaration, exported or not, is re-published as a global from inside the IIFE.

function exposeEntrypoint(entryPoint) {
  const entryAbs = resolve(entryPoint);
  return {
    name: "expose-entrypoint",
    setup(b) {
      b.onLoad({ filter: /\.ts$/ }, (args) => {
        if (args.path !== entryAbs) return null;
        const source = readFileSync(args.path, "utf8");
        const expose =
          '\n;if(typeof userFunction!=="undefined")globalThis.userFunction=userFunction;' +
          'if(typeof main!=="undefined")globalThis.main=main;\n';
        return { contents: source + expose, loader: "ts" };
      });
    },
  };
}

// Shared source files live outside each executable folder. Normal Node
// resolution would therefore walk upward and could select a conflicting root
// dependency. Resolve bare imports originating in shared/ from the current
// executable's package boundary so every bundle keeps its own dependency pins.
function resolveSharedDependencies(folder) {
  if (folder === "") return null;
  const sharedRoot = `${resolve("shared")}/`;
  return {
    name: "resolve-shared-dependencies",
    setup(b) {
      b.onResolve({ filter: /^[^./]/ }, async (args) => {
        if (
          args.pluginData?.resolvedSharedDependency ||
          !args.importer.startsWith(sharedRoot) ||
          args.path.startsWith("node:")
        ) {
          return null;
        }
        return b.resolve(args.path, {
          kind: args.kind,
          resolveDir: resolve(folder),
          pluginData: { resolvedSharedDependency: true },
          with: args.with,
        });
      });
    },
  };
}

// The runner preloads LangChain and exposes the registry-backed Wonderful
// adapters on globalThis. Functions must reference those runtime instances
// instead of bundling the Node-oriented LangChain SDK into the WASM script.
const langchainGlobals = {
  name: "resolve-langchain-globals",
  setup(b) {
    b.onResolve({ filter: /^@wonderful\/types\/langchain$/ }, () => ({
      path: "langchain-globals",
      namespace: "wonderful-types-langchain-shim",
    }));
    b.onLoad({ filter: /.*/, namespace: "wonderful-types-langchain-shim" }, () => ({
      contents: `
exports.LangChainOpenAI = globalThis.LangChainOpenAI;
exports.LangChainAnthropic = globalThis.LangChainAnthropic;
exports.LangChainGoogleGenAI = globalThis.LangChainGoogleGenAI;
exports.ModelProfiles = globalThis.ModelProfiles;
exports.LangChainCore = globalThis.LangChainCore;
`,
      loader: "js",
    }));
  },
};

function hasUnicodePropertyEscapes(source) {
  return source.includes("\\p{") || source.includes("\\P{");
}

function hasBuildDependencies(names) {
  if (!existsSync("package.json")) return false;
  const packageJSON = JSON.parse(readFileSync("package.json", "utf8"));
  return names.every((name) => Boolean(packageJSON.dependencies?.[name]));
}

function regexLiteralSource(pattern, flags) {
  return new RegExp(pattern, flags).toString();
}

function regexConstructorSource(node, pattern, flags) {
  const prefix = node.type === "NewExpression" ? "new " : "";
  return `${prefix}RegExp(${JSON.stringify(pattern)}, ${JSON.stringify(flags)})`;
}

async function transpileUnicodePropertyEscapes(source) {
  if (!hasUnicodePropertyEscapes(source)) {
    return { source, transformed: 0 };
  }
  [parseJavaScript, rewritePattern] = await Promise.all([
    parseJavaScript ?? import("wonderful-internal-acorn").then(({ parse }) => parse),
    rewritePattern ??
      import("wonderful-internal-regexpu-core").then(({ default: rewrite }) => rewrite),
  ]);

  const replacements = [];
  const rewrite = (node, pattern, flags) => {
    if ((!flags.includes("u") && !flags.includes("v")) || !hasUnicodePropertyEscapes(pattern)) return;
    let rewrittenFlags = flags;
    const options = {
      unicodePropertyEscapes: "transform",
      onNewFlags(flags) {
        rewrittenFlags = flags;
      },
    };
    if (flags.includes("v")) {
      options.unicodeSetsFlag = "transform";
    }
    const rewritten = rewritePattern(pattern, flags, options);
    replacements.push({
      start: node.start,
      end: node.end,
      source:
        node.type === "Literal"
          ? regexLiteralSource(rewritten, rewrittenFlags)
          : regexConstructorSource(node, rewritten, rewrittenFlags),
    });
  };

  const ast = parseJavaScript(source, {
    ecmaVersion: "latest",
    sourceType: "script",
    ranges: true,
  });
  const constructorCandidates = [];
  const visit = (node) => {
    if (Array.isArray(node)) {
      for (const child of node) visit(child);
      return;
    }
    if (!node || typeof node !== "object") return;

    if (node.type === "Literal" && node.regex) {
      rewrite(node, node.regex.pattern, node.regex.flags);
    } else if (
      (node.type === "NewExpression" || node.type === "CallExpression") &&
      node.callee?.type === "Identifier" &&
      node.callee.name === "RegExp" &&
      node.arguments?.length >= 2 &&
      typeof node.arguments[0]?.value === "string" &&
      typeof node.arguments[1]?.value === "string" &&
      hasUnicodePropertyEscapes(node.arguments[0].value) &&
      (node.arguments[1].value.includes("u") || node.arguments[1].value.includes("v"))
    ) {
      constructorCandidates.push(node);
    }

    for (const child of Object.values(node)) {
      visit(child);
    }
  };

  visit(ast);
  if (constructorCandidates.length > 0) {
    analyzeJavaScriptScopes ??= await import("wonderful-internal-eslint-scope").then(
      ({ analyze }) => analyze,
    );
    const scopeManager = analyzeJavaScriptScopes(ast, {
      ecmaVersion: 2024,
      sourceType: "script",
    });
    const globalRegExpReferences = new WeakSet();
    for (const scope of scopeManager.scopes) {
      for (const reference of scope.references) {
        let hasDynamicScope = reference.tainted;
        for (let current = reference.from; current && !hasDynamicScope; current = current.upper) {
          hasDynamicScope = current.type === "with" || current.directCallToEvalScope;
        }
        if (
          reference.identifier.name === "RegExp" &&
          reference.resolved === null &&
          !hasDynamicScope
        ) {
          globalRegExpReferences.add(reference.identifier);
        }
      }
    }
    for (const node of constructorCandidates) {
      if (globalRegExpReferences.has(node.callee)) {
        rewrite(node, node.arguments[0].value, node.arguments[1].value);
      }
    }
  }

  replacements.sort((a, b) => b.start - a.start);
  for (const replacement of replacements) {
    source = source.slice(0, replacement.start) + replacement.source + source.slice(replacement.end);
  }
  return { source, transformed: replacements.length };
}

async function makeBundleRunnerCompatible(bundlePath, folder) {
  if (!existsSync(bundlePath)) return;
  const original = readFileSync(bundlePath, "utf8");
  if (!hasUnicodePropertyEscapes(original)) return;
  if (!unicodeRegexTransformerAvailable) {
    console.error(
      `[warning] ${folder || "."} bundles a Unicode property escape but the transformer is unavailable; the runner will reject this bundle`,
    );
    return;
  }
  try {
    const { source, transformed } = await transpileUnicodePropertyEscapes(original);
    if (transformed > 0) {
      writeFileSync(bundlePath, source);
      // This post-build rewrite changes generated columns after esbuild has
      // emitted its map. A stale map is worse than no map, so fall back to the
      // legacy generated locations for this uncommon compatibility path.
      rmSync(`${bundlePath}.map`, { force: true });
      console.log(`transpiled ${transformed} Unicode RegExp pattern(s) in ${folder || "."}`);
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`transpile Unicode RegExp patterns in ${folder || "."}: ${message}`);
  }
}

async function buildFolder(folder) {
  try {
    const dir = folder === "" ? "." : folder;
    const entryPoint = folder === "" ? "index.ts" : join(folder, "index.ts");
    if (!existsSync(join(dir, "config.json")) || !existsSync(entryPoint)) {
      throw new Error(`build target ${folder || "."} is not a function folder`);
    }
    const plugins = [langchainGlobals, resolveSharedDependencies(folder), exposeEntrypoint(entryPoint)].filter(Boolean);
    await build({
      entryPoints: [entryPoint],
      bundle: true,
      platform: "node",
      format: "iife",
      target: "es2020",
      sourcemap: emitSourceMaps ? "external" : false,
      sourcesContent: false,
      outbase: ".",
      outdir: "dist",
      // Wonderful WIT imports are supplied by the runner component at execution
      // time. Keep them as imports instead of asking esbuild to resolve them as
      // npm packages while bundling a function.
      external: ["wonderful:llm/functions"],
      plugins,
      // A workspace install links each function's private dependencies below
      // its own folder. nodePaths also covers non-shared imports that need the
      // current executable's package boundary as a fallback.
      nodePaths: folder === "" ? [] : [resolve(folder, "node_modules")],
      // The entrypoint is reached only via the injected globalThis side effect;
      // keep tree shaking off so it is never dropped.
      treeShaking: false,
    });
    await makeBundleRunnerCompatible(join("dist", folder, "index.js"), folder);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`[function-build-error] ${JSON.stringify({ folder, message })}`);
    throw error;
  }
}

async function buildWithConcurrency(items, concurrency) {
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const index = next++;
      await buildFolder(items[index]);
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, worker));
}

const configuredConcurrency = Number.parseInt(process.env.WONDERFUL_BUILD_CONCURRENCY || "8", 10);
const concurrency = Number.isFinite(configuredConcurrency) && configuredConcurrency > 0 ? configuredConcurrency : 1;
await buildWithConcurrency(folders, concurrency);

console.log(`bundled ${folders.length} function(s)`);
