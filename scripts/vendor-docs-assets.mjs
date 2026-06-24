#!/usr/bin/env node
// Copies the third-party frontend libraries used by the Jekyll docs site out of
// node_modules and into docs/assets/vendor/ so the site can serve them locally
// instead of from a CDN. This is what brings these libraries under npm + Dependabot:
// bump the version in package.json and the next build re-copies the new files.
//
// The output directory (docs/assets/vendor/) is git-ignored and regenerated on every
// build — run `npm run docs:vendor` after `npm ci`, before `jekyll build`.

import { cpSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const modules = join(root, "node_modules");
const outDir = join(root, "docs", "assets", "vendor");

const assets = [
  ["jquery/dist/jquery.slim.min.js", "jquery/jquery.slim.min.js"],
  ["bootstrap/dist/css/bootstrap.min.css", "bootstrap/bootstrap.min.css"],
  ["bootstrap/dist/css/bootstrap.min.css.map", "bootstrap/bootstrap.min.css.map"],
  ["@fortawesome/fontawesome-free/css/all.min.css", "fontawesome/css/all.min.css"],
  ["@fortawesome/fontawesome-free/webfonts", "fontawesome/webfonts"],
];

rmSync(outDir, { recursive: true, force: true });

for (const [from, to] of assets) {
  const src = join(modules, from);
  const dest = join(outDir, to);
  mkdirSync(dirname(dest), { recursive: true });
  cpSync(src, dest, { recursive: true });
  console.log(`vendored ${to}`);
}
