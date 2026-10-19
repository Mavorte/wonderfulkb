#!/usr/bin/env node
// scripts/package-plugin.mjs — turn this app repository into a Wonderful Catalog
// plugin zip, so an app you built for your own tenant can be published for others.
//
//   pnpm package:plugin              # emit dist/<slug>-<version>.zip
//
// The plugin carries the repository itself: every file git would push (tracked
// plus untracked-but-not-ignored) goes under entities/<app>.app/repository/, and
// installing the plugin deploys that tree exactly like a push to the app's own
// repository — wonderful.json, app/, functions/ and tables/ are read by the same
// pipeline. Only the Catalog listing (manifest.json + media) is derived here, from
// wonderful.json's `catalog` block.

import { execFileSync } from "node:child_process";
import {
	cpSync,
	existsSync,
	mkdirSync,
	readFileSync,
	rmSync,
	writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const OUT_DIR = join(REPO_ROOT, "dist");
const STAGE_DIR = join(OUT_DIR, "plugin");

const VALID_CATEGORIES = [
	"Agents",
	"Monitoring",
	"Workflows",
	"Dev Tools",
	"Knowledge",
	"Other",
];

// Retired pre-2026-08 category names. Still accepted so a plugin repo scaffolded
// before the taxonomy change keeps packaging; the catalog folds them onto the
// current names on publish.
const DEPRECATED_CATEGORIES = [
	"Integrations",
	"Agent Skills",
	"Observability",
	"Industry Packs",
];

// How finished the plugin is — the author's own claim, so it lives in the manifest
// rather than being curated by a catalog admin. Optional.
const VALID_SOLUTION_TYPES = ["Working solution", "Demo / Inspiration"];

function fail(message) {
	console.error(`✖ ${message}`);
	process.exit(1);
}
function info(message) {
	console.log(`· ${message}`);
}
function ok(message) {
	console.log(`✓ ${message}`);
}

function readJson(path, label) {
	try {
		return JSON.parse(readFileSync(path, "utf8"));
	} catch (error) {
		fail(`${label} is not valid JSON: ${error.message}`);
	}
}

/** Reads wonderful.json and checks everything the catalog validator requires. */
function loadManifestSource() {
	const path = join(REPO_ROOT, "wonderful.json");
	if (!existsSync(path)) {
		fail("wonderful.json not found — run this from the root of an app repository");
	}
	const app = readJson(path, "wonderful.json");
	const catalog = app.catalog ?? {};

	const publisherId = (catalog.publisher_id ?? "").trim();
	if (!publisherId) {
		fail(
			"wonderful.json needs catalog.publisher_id to publish. Add a `catalog` block:\n" +
				'  "catalog": { "publisher_id": "acme", "slug": "acme/my-app", "version": "1.0.0", "category": "Other" }',
		);
	}

	// The catalog requires a scoped slug that agrees with publisher_id.
	const slug = (catalog.slug ?? `${publisherId}/${app.slug}`).trim();
	if (!slug.startsWith(`${publisherId}/`) || slug.split("/").length !== 2) {
		fail(`catalog.slug must be "<publisher>/<plugin>" and start with "${publisherId}/" (got "${slug}")`);
	}

	const version = (catalog.version ?? "").trim();
	if (!/^\d+\.\d+\.\d+(?:[-+].+)?$/.test(version)) {
		fail(`catalog.version must be semver (e.g. 1.0.0), got "${version || "(missing)"}"`);
	}

	const category = (catalog.category ?? "Other").trim();
	if (!VALID_CATEGORIES.includes(category) && !DEPRECATED_CATEGORIES.includes(category)) {
		fail(`catalog.category must be one of: ${VALID_CATEGORIES.join(", ")}`);
	}

	const solutionType = (catalog.solution_type ?? "").trim();
	if (solutionType && !VALID_SOLUTION_TYPES.includes(solutionType)) {
		fail(`catalog.solution_type must be one of: ${VALID_SOLUTION_TYPES.join(", ")}`);
	}

	const title = (catalog.title ?? app.name ?? "").trim();
	if (!title) fail("a title is required (catalog.title, or the app's name)");

	const shortDescription = (catalog.short_description ?? app.description ?? "").trim();
	if (!shortDescription) {
		fail("a short description is required (catalog.short_description, or the app's description)");
	}

	return { app, catalog, publisherId, slug, version, category, solutionType, title, shortDescription };
}

/** Lists every file a push of this repository would carry, relative to its root. */
function listRepositoryFiles() {
	let output;
	try {
		output = execFileSync("git", ["ls-files", "-z", "--cached", "--others", "--exclude-standard"], {
			cwd: REPO_ROOT,
			encoding: "utf8",
		});
	} catch {
		fail("git ls-files failed — package from inside the app's git repository");
	}
	return output
		.split("\0")
		.filter(Boolean)
		// This script's own output lands in dist/, which is not ignored.
		.filter((path) => !path.startsWith("dist/plugin/") && !/^dist\/[^/]+\.zip$/.test(path))
		.filter((path) => existsSync(join(REPO_ROOT, path)));
}

function writeStaged(relativePath, contents) {
	const target = join(STAGE_DIR, relativePath);
	mkdirSync(dirname(target), { recursive: true });
	writeFileSync(target, contents);
}

function main() {
	const source = loadManifestSource();
	const { app, catalog } = source;
	const appKey = app.slug;

	rmSync(STAGE_DIR, { recursive: true, force: true });
	mkdirSync(STAGE_DIR, { recursive: true });

	const appDir = `entities/${appKey}.app`;
	const repositoryDir = `${appDir}/repository`;
	const files = listRepositoryFiles();
	for (const path of files) {
		writeStaged(`${repositoryDir}/${path}`, readFileSync(join(REPO_ROOT, path)));
	}
	info(`packaged ${files.length} repository files`);
	writeStaged(
		`${appDir}/entity.json`,
		`${JSON.stringify({ name: app.name, description: app.description ?? "", repository_path: repositoryDir }, null, 2)}\n`,
	);
	const entities = [{ type: "app", key: appKey, path: `${appDir}/entity.json` }];

	// Media. README is required by the catalog; a screenshot is too. An icon is
	// optional — the catalog falls back to a per-category one.
	const readmePath = catalog.readme_path ?? "README.md";
	if (!existsSync(join(REPO_ROOT, readmePath))) {
		fail(`the catalog requires a readme: ${readmePath} not found (add one, or set catalog.readme_path)`);
	}
	cpSync(join(REPO_ROOT, readmePath), join(STAGE_DIR, readmePath));

	const screenshotPaths = catalog.screenshot_paths ?? [];
	if (!screenshotPaths.length) {
		fail(
			"the catalog requires at least one screenshot. Add images to the repo and list them:\n" +
				'  "catalog": { ..., "screenshot_paths": ["media/screenshots/01-overview.png"] }',
		);
	}
	for (const relativePath of screenshotPaths) {
		if (!existsSync(join(REPO_ROOT, relativePath))) {
			fail(`catalog.screenshot_paths references a missing file: ${relativePath}`);
		}
		mkdirSync(dirname(join(STAGE_DIR, relativePath)), { recursive: true });
		cpSync(join(REPO_ROOT, relativePath), join(STAGE_DIR, relativePath));
	}
	const iconPath = catalog.icon_path;
	if (iconPath) {
		if (!existsSync(join(REPO_ROOT, iconPath))) {
			fail(`catalog.icon_path references a missing file: ${iconPath}`);
		}
		mkdirSync(dirname(join(STAGE_DIR, iconPath)), { recursive: true });
		cpSync(join(REPO_ROOT, iconPath), join(STAGE_DIR, iconPath));
	}

	const manifest = {
		schema_version: 1,
		publisher_id: source.publisherId,
		slug: source.slug,
		version: source.version,
		title: source.title,
		short_description: source.shortDescription,
		category: source.category,
		...(source.solutionType ? { solution_type: source.solutionType } : {}),
		...(catalog.tags ? { tags: catalog.tags } : {}),
		...(iconPath ? { icon_path: iconPath } : {}),
		screenshot_paths: screenshotPaths,
		readme_path: readmePath,
		...(catalog.release_notes ? { release_notes: catalog.release_notes } : {}),
		// The service accounts install provisions; a function's config.json
		// `service_account` names one of them.
		...(catalog.required_service_accounts ? { required_service_accounts: catalog.required_service_accounts } : {}),
		entities,
	};
	writeStaged("manifest.json", `${JSON.stringify(manifest, null, 2)}\n`);

	const zipName = `${source.slug.replace("/", "-")}-${source.version}.zip`;
	const zipPath = join(OUT_DIR, zipName);
	rmSync(zipPath, { force: true });
	try {
		// `zip` rather than a node dependency: it is present in the sandbox image and
		// on any developer machine that can run git, and this repo's root toolchain
		// exists to bundle functions, not to package archives.
		execFileSync("zip", ["-rq", zipPath, "."], { cwd: STAGE_DIR, stdio: "inherit" });
	} catch (error) {
		fail(`could not create the zip (is \`zip\` installed?): ${error.message}`);
	}

	ok(`packaged ${zipName}`);
	console.log(`  entities: ${entities.map((e) => `${e.key} (${e.type})`).join(", ")}`);
	console.log("");
	console.log("  Install it on a tenant to try it:");
	console.log(
		`    curl -X POST "$WONDERFUL_BASE_URL/api/v1/catalog/plugins/dev-install" \\\n` +
			`      -H "X-api-key: $WONDERFUL_API_KEY" -F "file=@dist/${zipName}"`,
	);
}

main();
