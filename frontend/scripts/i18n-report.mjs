#!/usr/bin/env node
/**
 * i18n coverage report for the shoutrrr-logger frontend.
 *
 * Dependency-free (Node >= 18). Run from the `frontend/` directory:
 *
 *   pnpm i18n:check            # deterministic checks only (CI-grade)
 *   pnpm i18n:check --unused   # + advisory: catalog keys never referenced in code
 *   pnpm i18n:check --hardcoded# + advisory: heuristic hardcoded user-facing strings
 *   pnpm i18n:check --all      # everything
 *
 * Checks performed:
 *
 *   1. Catalog parity (HARD FAIL)
 *        Every non-default locale must have exactly the same key set as the
 *        default locale (`en`), for `messages/` and for each
 *        `plugins/<id>/locales/`. Reports missing and extra keys per locale.
 *
 *   2. Used-but-undefined keys (HARD FAIL)
 *        Every statically-resolvable `t('key')` / `t.rich('key')` reference in
 *        the source must resolve to a key defined in the default-locale catalog
 *        (taking the surrounding `useTranslations("NS")` namespace into account).
 *        Catches typos and keys that were used but never added to the catalog.
 *
 *   3. Unused catalog keys (ADVISORY, --unused)
 *        Default-locale keys whose leaf name is never referenced by any static
 *        `t('...')` call. Heuristic — dynamic keys built with template literals
 *        (e.g. t(`timePresets.${v}`)) produce false positives, so this never
 *        fails the build.
 *
 *   4. Hardcoded user-facing strings (ADVISORY, --hardcoded)
 *        Heuristic scan for literal prose in `placeholder=`, `aria-label=`,
 *        `title=` attributes and `toast.*("...")` calls that does not go through
 *        a translation function. Expect false positives; advisory only.
 *
 * Exit code is non-zero if any HARD FAIL check finds problems, so this is safe
 * to wire into CI (e.g. alongside `pnpm lint`).
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const FRONTEND_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DEFAULT_LOCALE = "en";

const args = new Set(process.argv.slice(2));
const SHOW_UNUSED = args.has("--unused") || args.has("--all");
const SHOW_HARDCODED = args.has("--hardcoded") || args.has("--all");

// ── small ANSI helpers (no dependency) ───────────────────────────────────────
const useColor = process.stdout.isTTY && !args.has("--no-color");
const c = (code, s) => (useColor ? `\x1b[${code}m${s}\x1b[0m` : s);
const red = (s) => c("31", s);
const green = (s) => c("32", s);
const yellow = (s) => c("33", s);
const cyan = (s) => c("36", s);
const bold = (s) => c("1", s);

// ── JSON catalog helpers ─────────────────────────────────────────────────────

/** Flatten a nested messages object into a Set of dotted leaf keys. */
function flattenKeys(obj, prefix = "", out = new Set()) {
  for (const [key, value] of Object.entries(obj)) {
    const full = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      flattenKeys(value, full, out);
    } else {
      out.add(full);
    }
  }
  return out;
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

/**
 * A catalog group is a logical set of locale files that must stay in parity,
 * plus the namespace prefix that its keys live under at runtime.
 */
function discoverCatalogGroups() {
  const groups = [];

  // Core messages: messages/<locale>.json, keys used verbatim (top-level namespaces).
  const messagesDir = path.join(FRONTEND_ROOT, "messages");
  groups.push({
    label: "messages",
    dir: messagesDir,
    prefix: "", // keys already include their namespace, e.g. "NotificationLog.title"
    locales: localeFilesIn(messagesDir),
  });

  // Plugin locales: plugins/<id>/locales/<locale>.json, runtime namespace "Plugin_<id>".
  const pluginsDir = path.join(FRONTEND_ROOT, "plugins");
  if (fs.existsSync(pluginsDir)) {
    for (const id of fs.readdirSync(pluginsDir)) {
      const localesDir = path.join(pluginsDir, id, "locales");
      if (fs.existsSync(localesDir)) {
        groups.push({
          label: `plugins/${id}`,
          dir: localesDir,
          prefix: `Plugin_${id}`,
          locales: localeFilesIn(localesDir),
        });
      }
    }
  }

  return groups;
}

function localeFilesIn(dir) {
  const map = {};
  for (const f of fs.readdirSync(dir)) {
    if (f.endsWith(".json")) map[f.replace(/\.json$/, "")] = path.join(dir, f);
  }
  return map;
}

// ── source scanning ──────────────────────────────────────────────────────────

const SOURCE_DIRS = ["app", "components", "lib", "plugins"];
const SOURCE_EXT = /\.(tsx?|jsx?)$/;
const IGNORE_DIRS = new Set(["node_modules", ".next", "dist", "build", "locales"]);

function walkSourceFiles() {
  const files = [];
  const walk = (dir) => {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        if (!IGNORE_DIRS.has(entry.name)) walk(path.join(dir, entry.name));
      } else if (SOURCE_EXT.test(entry.name)) {
        files.push(path.join(dir, entry.name));
      }
    }
  };
  for (const d of SOURCE_DIRS) walk(path.join(FRONTEND_ROOT, d));
  return files;
}

const RE_NAMESPACE = /(?:useTranslations|getTranslations)\(\s*["'`]([^"'`]+)["'`]/g;
const RE_STATIC_T = /\bt(?:\.rich)?\(\s*["']([^"']+)["']/g;
const RE_DYNAMIC_T = /\bt(?:\.rich)?\(\s*`/g;

function scanSource() {
  const used = []; // { file, ns: string[], key }
  const dynamic = []; // { file }
  for (const file of walkSourceFiles()) {
    const text = fs.readFileSync(file, "utf8");
    const rel = path.relative(FRONTEND_ROOT, file);

    const namespaces = [...text.matchAll(RE_NAMESPACE)].map((m) => m[1]);
    for (const m of text.matchAll(RE_STATIC_T)) {
      used.push({ file: rel, ns: namespaces, key: m[1] });
    }
    if (RE_DYNAMIC_T.test(text)) dynamic.push({ file: rel });
    RE_DYNAMIC_T.lastIndex = 0;
  }
  return { used, dynamic };
}

// ── hardcoded-string heuristic ───────────────────────────────────────────────

// Attribute literals (placeholder/aria-label/title) and toast calls with raw prose.
const RE_ATTR_LITERAL = /\b(placeholder|aria-label|title)=("([^"]*)"|'([^']*)')/g;
const RE_TOAST_LITERAL = /\btoast\.(?:success|error|info|warning|message)\(\s*["']([^"']+)["']/g;

// Values that are language-neutral and intentionally not translated.
const HARDCODED_ALLOW = [
  /^https?:\/\//i, // example URLs
  /^[:#@/.\-_\s]*$/, // punctuation/symbols only
  /^\{[^}]+\}/, // template placeholders like {title}
  /^[A-Za-z0-9_.-]+:[A-Za-z0-9_.*?/|-]+$/, // search-syntax examples e.g. sender:gitlab
  /^[a-z0-9_]+$/, // single identifier tokens (field names, etc.)
];

function looksHardcodedProse(value) {
  const v = value.trim();
  if (v.length < 4) return false;
  if (!/[A-Za-z]/.test(v)) return false;
  if (HARDCODED_ALLOW.some((re) => re.test(v))) return false;
  // Require at least one space OR a capitalized word — prose, not a token.
  return /\s/.test(v) || /^[A-Z][a-z]+/.test(v);
}

function scanHardcoded() {
  const hits = [];
  for (const file of walkSourceFiles()) {
    if (!file.endsWith(".tsx")) continue;
    const rel = path.relative(FRONTEND_ROOT, file);
    const text = fs.readFileSync(file, "utf8");
    const lines = text.split("\n");
    lines.forEach((line, i) => {
      for (const m of line.matchAll(RE_ATTR_LITERAL)) {
        const val = m[3] ?? m[4] ?? "";
        if (looksHardcodedProse(val)) {
          hits.push({ file: rel, line: i + 1, kind: m[1], value: val });
        }
      }
      for (const m of line.matchAll(RE_TOAST_LITERAL)) {
        if (looksHardcodedProse(m[1])) {
          hits.push({ file: rel, line: i + 1, kind: "toast", value: m[1] });
        }
      }
    });
  }
  return hits;
}

// ── report ───────────────────────────────────────────────────────────────────

function main() {
  let hardFailures = 0;
  const groups = discoverCatalogGroups();

  console.log(bold("\ni18n coverage report\n" + "=".repeat(60)));

  // Default-locale key universe (with runtime namespace prefixes applied).
  const definedKeys = new Set();
  const defaultKeysByGroup = {};
  for (const g of groups) {
    const defFile = g.locales[DEFAULT_LOCALE];
    if (!defFile) {
      console.log(red(`\n✖ ${g.label}: missing default locale '${DEFAULT_LOCALE}.json'`));
      hardFailures++;
      continue;
    }
    const keys = flattenKeys(readJson(defFile));
    defaultKeysByGroup[g.label] = keys;
    for (const k of keys) definedKeys.add(g.prefix ? `${g.prefix}.${k}` : k);
  }

  // ── 1. Parity ───────────────────────────────────────────────────────────
  console.log(bold("\n1. Catalog parity"));
  let parityOk = true;
  for (const g of groups) {
    const def = defaultKeysByGroup[g.label];
    if (!def) continue;
    for (const [locale, file] of Object.entries(g.locales)) {
      if (locale === DEFAULT_LOCALE) continue;
      const keys = flattenKeys(readJson(file));
      const missing = [...def].filter((k) => !keys.has(k)).sort();
      const extra = [...keys].filter((k) => !def.has(k)).sort();
      if (missing.length === 0 && extra.length === 0) {
        console.log(green(`  ✓ ${g.label} [${locale}] — ${keys.size} keys, full parity`));
      } else {
        parityOk = false;
        hardFailures++;
        console.log(red(`  ✖ ${g.label} [${locale}] — ${missing.length} missing, ${extra.length} extra`));
        missing.forEach((k) => console.log(red(`      missing: ${k}`)));
        extra.forEach((k) => console.log(yellow(`      extra:   ${k}`)));
      }
    }
  }
  if (parityOk) console.log(green("  All catalogs at full parity."));

  // ── 2. Used-but-undefined ────────────────────────────────────────────────
  console.log(bold("\n2. Keys referenced in code"));
  const { used, dynamic } = scanSource();
  const undefinedRefs = [];
  for (const u of used) {
    if (u.ns.length === 0) continue; // can't resolve namespace; skip (no false positive)
    const resolved = u.ns.some((ns) => definedKeys.has(`${ns}.${u.key}`));
    if (!resolved) undefinedRefs.push(u);
  }
  if (undefinedRefs.length === 0) {
    console.log(green(`  ✓ ${used.length} static references all resolve to defined keys.`));
  } else {
    hardFailures++;
    console.log(red(`  ✖ ${undefinedRefs.length} reference(s) do not resolve to any defined key:`));
    for (const u of undefinedRefs) {
      console.log(red(`      ${u.file}: t('${u.key}')  (namespaces: ${u.ns.join(", ") || "none"})`));
    }
  }
  if (dynamic.length > 0) {
    console.log(cyan(`  ℹ ${dynamic.length} file(s) use dynamic t(\`...\`) keys (not statically verifiable):`));
    for (const d of dynamic) console.log(cyan(`      ${d.file}`));
  }

  // ── 3. Unused (advisory) ─────────────────────────────────────────────────
  if (SHOW_UNUSED) {
    console.log(bold("\n3. Unused catalog keys (advisory — expect dynamic-key false positives)"));
    const usedLeaves = new Set(used.map((u) => u.key.split(".").pop()));
    let unusedCount = 0;
    for (const k of definedKeys) {
      const leaf = k.split(".").pop();
      if (!usedLeaves.has(leaf)) {
        unusedCount++;
        console.log(yellow(`      unused?: ${k}`));
      }
    }
    if (unusedCount === 0) console.log(green("  No obviously-unused keys."));
    else console.log(cyan(`  ${unusedCount} candidate(s) — review manually before deleting.`));
  }

  // ── 4. Hardcoded strings (advisory) ──────────────────────────────────────
  if (SHOW_HARDCODED) {
    console.log(bold("\n4. Hardcoded user-facing strings (advisory — heuristic)"));
    const hits = scanHardcoded();
    if (hits.length === 0) {
      console.log(green("  No likely-hardcoded prose found."));
    } else {
      for (const h of hits) {
        console.log(yellow(`      ${h.file}:${h.line} [${h.kind}] "${h.value}"`));
      }
      console.log(cyan(`  ${hits.length} candidate(s) — verify; some may be intentional.`));
    }
  }

  // ── summary ───────────────────────────────────────────────────────────────
  console.log(bold("\n" + "=".repeat(60)));
  if (hardFailures === 0) {
    console.log(green(bold("✓ i18n checks passed.")) + "\n");
    process.exit(0);
  } else {
    console.log(red(bold(`✖ i18n checks failed (${hardFailures} problem group(s)).`)) + "\n");
    process.exit(1);
  }
}

main();
