#!/usr/bin/env node
// Cut a new release: set the version across every manifest, regenerate the changelog,
// commit, and create the matching git tag. Does NOT push by default — pushing the tag is
// what triggers the GitHub release workflow.
//
// The version lives in six places (three plugin manifests, two marketplace manifests, and
// package.json), so this script is their single writer. Hand-editing is how they drift.
//
// Usage:
//   node scripts/release.mjs 0.8.0            # bump + changelog + commit + tag (local only)
//   node scripts/release.mjs 0.8.0 --push     # also push the branch and the tag
//   node scripts/release.mjs 0.8.0 --dry-run  # print what would happen, change nothing

import { execSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");

const args = process.argv.slice(2);
const dryRun = args.includes("--dry-run");
const push = args.includes("--push");
const version = args.find((a) => !a.startsWith("--"));

if (!version || !/^\d+\.\d+\.\d+$/.test(version)) {
  console.error("Usage: node scripts/release.mjs <x.y.z> [--push] [--dry-run]");
  process.exit(1);
}

const tag = `v${version}`;

const run = (cmd) => {
  console.log(`$ ${cmd}`);
  if (!dryRun) execSync(cmd, { stdio: "inherit", cwd: repoRoot });
};

// Refuse to release with a dirty tree (the bump/changelog must be the only changes).
const status = execSync("git status --porcelain", { encoding: "utf8", cwd: repoRoot }).trim();
if (status && !dryRun) {
  console.error("Working tree is not clean — commit or stash changes first:\n" + status);
  process.exit(1);
}

if (execSync(`git tag -l ${tag}`, { encoding: "utf8", cwd: repoRoot }).trim()) {
  console.error(`Tag ${tag} already exists.`);
  process.exit(1);
}

console.log(`Releasing ${tag}`);

// 1. Write the version into every manifest that carries one.
//    Plugin manifests hold it at the top level; marketplace manifests repeat it per plugin
//    entry (and once in metadata).
const MANIFESTS = [
  ".claude-plugin/plugin.json",
  ".claude-plugin/marketplace.json",
  ".codex-plugin/plugin.json",
  ".codex-plugin/marketplace.json",
  ".cursor-plugin/plugin.json",
  "package.json",
];

for (const rel of MANIFESTS) {
  const file = path.join(repoRoot, rel);
  const data = JSON.parse(readFileSync(file, "utf8"));
  if (Array.isArray(data.plugins)) {
    if (data.metadata) data.metadata.version = version;
    for (const plugin of data.plugins) plugin.version = version;
  } else {
    data.version = version;
  }
  console.log(`version ${version} -> ${rel}`);
  if (!dryRun) writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
}

// 2. Regenerate the changelog from the tags.
run("npx git-cliff --tag " + tag + " -o CHANGELOG.md");

// 3. Commit and tag.
run(`git add ${MANIFESTS.join(" ")} CHANGELOG.md`);
run(`git commit -m "chore(release): ${tag}"`);
run(`git tag -a ${tag} -m "${tag}"`);

// 4. Optionally push (this triggers .github/workflows/release.yml).
if (push) {
  run("git push");
  run(`git push origin ${tag}`);
  console.log(`\nPushed ${tag} — the Release workflow will publish the GitHub release.`);
} else {
  console.log(`\nLocal release ready. To publish, run:\n  git push && git push origin ${tag}`);
}
