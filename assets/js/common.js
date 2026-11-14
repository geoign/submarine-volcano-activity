// Shared by every page: language, header and footer, data loading, small formatters.

import { STRINGS, COUNTRY_JA } from "./i18n.js";

export const CLASSES = ["known", "likely", "possible", "recurrent", "airborne", "undetermined", "nonvolcanic", "unreviewed"];
export const RANK = Object.fromEntries(CLASSES.map((c, i) => [c, i]));
export const DB = "db/";

// ---------------------------------------------------------------- language and theme

function store(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch { /* storage may be blocked; the page works without it */ }
  return null;
}

function initialLang() {
  const q = new URLSearchParams(location.search).get("lang");
  if (q === "ja" || q === "en") return q;
  const saved = store("lang");
  if (saved === "ja" || saved === "en") return saved;
  return (navigator.language || "en").toLowerCase().startsWith("ja") ? "ja" : "en";
}

export let LANG = initialLang();
document.documentElement.dataset.lang = LANG;
document.documentElement.lang = LANG;
const savedTheme = store("theme");
if (savedTheme === "light" || savedTheme === "dark") document.documentElement.dataset.theme = savedTheme;

export function t(key, vars) {
  let s = (STRINGS[LANG] && STRINGS[LANG][key]) ?? STRINGS.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
}

const langListeners = [];
export function onLang(fn) { langListeners.push(fn); }

export function setLang(lang) {
  LANG = lang;
  store("lang", lang);
  document.documentElement.dataset.lang = lang;
  document.documentElement.lang = lang;
  applyI18n(document);
  for (const fn of langListeners) fn(lang);
}

export function applyI18n(root) {
  for (const el of root.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  for (const el of root.querySelectorAll("[data-i18n-placeholder]")) el.placeholder = t(el.dataset.i18nPlaceholder);
  for (const el of root.querySelectorAll("[data-i18n-label]")) el.setAttribute("aria-label", t(el.dataset.i18nLabel));
  const page = document.body.dataset.title;
  document.title = (page ? t(page) + " · " : "") + t("site.title");
}

export function isDark() {
  const forced = document.documentElement.dataset.theme;
  if (forced) return forced === "dark";
  return matchMedia("(prefers-color-scheme: dark)").matches;
}

const themeListeners = [];
export function onTheme(fn) { themeListeners.push(fn); }
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => themeListeners.forEach((fn) => fn()));

export function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// ---------------------------------------------------------------- DOM helpers

export function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k === "dataset") Object.assign(node.dataset, v);
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return node;
}

export function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); return node; }

/** Append children, leaving out null, undefined and false (DOM append would print them). */
export function add(node, ...children) {
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) node.append(c);
  return node;
}

const ICON = '<svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="7" fill="#1c5cab"/><path d="M4 22c3-2 5-2 8 0s5 2 8 0 5-2 8 0v6H4z" fill="#86b6ef"/><path d="M10 21l4.5-9h3L22 21z" fill="#f0efec"/><circle cx="16" cy="8" r="2.2" fill="#f0946a"/></svg>';

export function renderChrome(active) {
  const header = el("header", { class: "site-header" });
  const brand = el("a", { class: "brand", href: "index.html" });
  brand.innerHTML = ICON;
  brand.append(el("span", { dataset: { i18n: "site.title" } }));
  const nav = el("nav", { "aria-label": "Site" },
    ...[["map", "index.html"], ["episodes", "episodes.html"], ["about", "about.html"]].map(([key, href]) =>
      el("a", { href, "aria-current": key === active ? "page" : null, dataset: { i18n: `nav.${key}` } })));
  const tools = el("div", { class: "tools" },
    el("button", { type: "button", dataset: { i18n: "nav.lang" }, onclick: () => setLang(LANG === "ja" ? "en" : "ja") }),
    el("button", {
      type: "button", dataset: { i18n: "nav.theme" },
      onclick: () => {
        const next = isDark() ? "light" : "dark";
        document.documentElement.dataset.theme = next;
        store("theme", next);
        themeListeners.forEach((fn) => fn());
      },
    }));
  header.append(brand, nav, tools);
  document.body.prepend(header);
  const footer = el("footer", { class: "site-footer" },
    el("div", { dataset: { i18n: "footer.text" } }), el("div", { id: "footer-updated" }));
  document.body.append(footer);
  applyI18n(document);
  loadJSON(DB + "meta.json").then((meta) => {
    const show = () => { document.getElementById("footer-updated").textContent = t("footer.updated", { last: meta.last_pass, built: meta.generated.slice(0, 10) }); };
    show();
    onLang(show);
  }).catch(() => {});
}

// ---------------------------------------------------------------- data

const cache = new Map();

export function loadJSON(url) {
  if (!cache.has(url)) {
    cache.set(url, fetch(url).then((r) => {
      if (!r.ok) throw new Error(`${url}: ${r.status}`);
      return r.json();
    }));
  }
  return cache.get(url);
}

/** Parse RFC 4180 CSV text into an array of objects keyed by the header row. */
export function parseCSV(text) {
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  const rows = [];
  let row = [], field = "", i = 0, quoted = false;
  const n = text.length;
  while (i < n) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"') {
        if (text[i + 1] === '"') { field += '"'; i += 2; continue; }
        quoted = false; i++; continue;
      }
      field += ch; i++; continue;
    }
    if (ch === '"') { quoted = true; i++; continue; }
    if (ch === ",") { row.push(field); field = ""; i++; continue; }
    if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(field); rows.push(row); row = []; field = ""; i++; continue;
    }
    field += ch; i++;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  const head = rows.shift() || [];
  return rows.filter((r) => r.length > 1 || r[0] !== "").map((r) => Object.fromEntries(head.map((h, k) => [h, r[k] ?? ""])));
}

export function loadCSV(url, { optional = false } = {}) {
  if (!cache.has(url)) {
    cache.set(url, fetch(url).then((r) => {
      if (!r.ok) {
        if (optional && r.status === 404) return [];
        throw new Error(`${url}: ${r.status}`);
      }
      return r.text().then(parseCSV);
    }));
  }
  return cache.get(url);
}

export function toCSV(columns, rows) {
  const q = (v) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
  };
  return [columns.join(","), ...rows.map((r) => columns.map((c) => q(r[c])).join(","))].join("\n") + "\n";
}

export function download(name, text, type = "text/csv") {
  const url = URL.createObjectURL(new Blob([text], { type: type + ";charset=utf-8" }));
  const a = el("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---------------------------------------------------------------- formatting

export function volcanoName(v) {
  const ja = v.name_ja;
  return LANG === "ja" && ja ? ja : v.name;
}
export function volcanoAlt(v) {
  const ja = v.name_ja;
  return LANG === "ja" && ja ? v.name : (ja || "");
}
export function countryName(c) { return LANG === "ja" ? (COUNTRY_JA[c] || c) : c; }
export function classLabel(c, short = false) { return t((short ? "class.short." : "class.") + (c || "none")); }

export function classBadge(c, short = false) {
  return el("span", { class: "badge" }, el("i", { class: `dot ${c || "none"}` }), classLabel(c, short));
}

export function phenomena(code) {
  return (code || "").split("+").filter(Boolean).map((p) => t("ph." + p)).join(LANG === "ja" ? "、" : ", ");
}

export function fmtNum(v, digits = 1) {
  if (v === "" || v === null || v === undefined) return "";
  const x = Number(v);
  if (!Number.isFinite(x)) return "";
  if (x !== 0 && Math.abs(x) < 0.1) return x.toFixed(2);
  return x.toLocaleString(LANG === "ja" ? "ja-JP" : "en-GB", { maximumFractionDigits: digits });
}
export function fmtInt(v) { return Number(v || 0).toLocaleString(LANG === "ja" ? "ja-JP" : "en-GB"); }
export function fmtLatLon(lat, lon) {
  const a = Number(lat), o = Number(lon);
  return `${Math.abs(a).toFixed(3)}°${a >= 0 ? "N" : "S"}, ${Math.abs(o).toFixed(3)}°${o >= 0 ? "E" : "W"}`;
}
export function dateRange(a, b) { return a === b || !b ? a : `${a} – ${b}`; }

/** The text of a note in the chosen language; falls back to the other one. */
export function noteText(row, base) {
  const en = row[base + "_en"], ja = row[base + "_ja"];
  if (LANG === "ja") return { text: ja || en || "", fallback: !ja && !!en };
  return { text: en || ja || "", fallback: !en && !!ja };
}

/** URL of the quicklook of a high-resolution pass. */
export function quicklookURL(base, p) {
  const tt = p.time;
  const stamp = tt.slice(0, 4) + tt.slice(5, 7) + tt.slice(8, 10) + "T" + tt.slice(11, 13) + tt.slice(14, 16);
  return `${base}/ql/${p.zone_id}/${p.zone_id}_${stamp}_${p.sat}.jpg`;
}

export function showError(container, err) {
  console.error(err);
  clear(container).append(el("p", { class: "error", text: t("error.load") + " " + (err && err.message ? err.message : "") }));
}
