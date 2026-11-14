// Episode table: every episode of the database, filtered and sorted in the browser.

import {
  CLASSES, RANK, DB, LANG, t, el, clear, renderChrome, loadCSV, onLang, applyI18n, volcanoName, countryName,
  classLabel, classBadge, phenomena, fmtNum, noteText, toCSV, download, showError,
} from "./common.js";

renderChrome("episodes");

const $ = (x) => document.getElementById(x);
const PAGE = 100;
const S = {
  q: "", y0: "", y1: "", tier: "", status: "", page: 0, sort: "start", dir: -1,
  shown: new Set(CLASSES.filter((c) => c !== "nonvolcanic")),
};
let rows = [], volcano = new Map(), view = [];

const COLS = [
  ["volcano", "e.col.volcano", false], ["start", "e.col.start", false], ["end", "e.col.end", false],
  ["class", "e.col.class", false], ["phenomena", "e.col.phenomena", false], ["max_dw_km2", "e.col.maxdw", true],
  ["n_detect", "e.col.n", true], ["sensors", "e.col.sensors", false], ["note", "e.col.note", false],
];

function sortKey(e, key) {
  if (key === "volcano") return volcanoName(volcano.get(e.volcano_id)).toLowerCase();
  if (key === "class") return RANK[e.class];
  if (key === "max_dw_km2" || key === "n_detect") return Number(e[key] || 0);
  if (key === "note") return noteText(e, "note").text;
  return e[key] || "";
}

function filter() {
  const q = S.q.trim().toLowerCase();
  view = rows.filter((e) => {
    if (!S.shown.has(e.class)) return false;
    if (S.tier && e.tier !== S.tier) return false;
    if (S.status && e.review_status !== S.status) return false;
    if (S.y0 && e.end.slice(0, 4) < S.y0) return false;
    if (S.y1 && e.start.slice(0, 4) > S.y1) return false;
    if (q) {
      const v = volcano.get(e.volcano_id);
      const hay = [v.name, v.name_ja, v.country, countryName(v.country), e.episode_id, e.note_en, e.note_ja, e.known_ref].join("\n").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  view.sort((a, b) => {
    const x = sortKey(a, S.sort), y = sortKey(b, S.sort);
    return (x < y ? -1 : x > y ? 1 : 0) * S.dir || (a.start < b.start ? 1 : -1);
  });
}

function drawChips() {
  const count = Object.fromEntries(CLASSES.map((c) => [c, 0]));
  for (const e of rows) count[e.class]++;
  clear($("classes")).append(...CLASSES.map((c) => el("button", {
    type: "button", class: "chip", "aria-pressed": String(S.shown.has(c)),
    onclick: () => { S.shown.has(c) ? S.shown.delete(c) : S.shown.add(c); S.page = 0; draw(); },
  }, el("i", { class: `dot ${c}` }), `${classLabel(c)} (${count[c].toLocaleString()})`)));
}

function drawTable() {
  const pages = Math.max(1, Math.ceil(view.length / PAGE));
  S.page = Math.min(S.page, pages - 1);
  $("count").textContent = t("e.count", { n: view.length.toLocaleString() });
  $("page").textContent = t("e.page", { p: S.page + 1, n: pages });
  $("prev").disabled = S.page === 0;
  $("next").disabled = S.page >= pages - 1;
  const head = el("thead", {}, el("tr", {}, ...COLS.map(([key, label, numeric]) => el("th", { class: numeric ? "num" : null, "aria-sort": S.sort === key ? (S.dir > 0 ? "ascending" : "descending") : null },
    el("button", { type: "button", onclick: () => { if (S.sort === key) S.dir = -S.dir; else { S.sort = key; S.dir = key === "volcano" ? 1 : -1; } draw(); } },
      t(label), S.sort === key ? (S.dir > 0 ? " ▲" : " ▼") : "")))));
  const body = el("tbody");
  for (const e of view.slice(S.page * PAGE, (S.page + 1) * PAGE)) {
    const v = volcano.get(e.volcano_id);
    const note = noteText(e, "note");
    const cause = e.class === "nonvolcanic" && e.cause ? t("cause." + e.cause) : "";
    const text = [cause, note.fallback && LANG === "en" && cause ? "" : note.text].filter(Boolean).join(LANG === "ja" ? "。" : ". ");
    body.append(el("tr", {},
      el("td", {}, el("a", { href: `volcano.html?id=${encodeURIComponent(e.volcano_id)}&ep=${encodeURIComponent(e.episode_id)}`, text: volcanoName(v) }),
        el("div", { class: "notice", style: "font-size:.78rem", text: countryName(v.country) })),
      el("td", { class: "nowrap", text: e.start }), el("td", { class: "nowrap", text: e.end }),
      el("td", {}, classBadge(e.class, true), e.tier === "lowres" ? el("div", {}, el("span", { class: "tag", text: t("tier.lowres") })) : null,
        e.review_status === "human-reviewed" ? el("div", {}, el("span", { class: "tag human", text: t("status.human-reviewed") })) : null),
      el("td", { text: phenomena(e.phenomena) }),
      el("td", { class: "num", text: fmtNum(e.max_dw_km2, 2) }),
      el("td", { class: "num", text: `${e.n_detect} / ${e.n_seen}` }),
      el("td", { text: e.sensors }),
      el("td", { class: "note", text: text.length > 260 ? text.slice(0, 260) + "…" : text })));
  }
  if (!view.length) body.append(el("tr", {}, el("td", { colspan: COLS.length, text: t("e.none") })));
  clear($("table")).append(head, body);
}

function draw() { filter(); drawChips(); drawTable(); }

async function main() {
  const [eps, vols] = await Promise.all([loadCSV(DB + "episodes.csv"), loadCSV(DB + "volcanoes.csv")]);
  rows = eps;
  volcano = new Map(vols.map((v) => [v.volcano_id, v]));
  const years = [...new Set(rows.flatMap((e) => [e.start.slice(0, 4), e.end.slice(0, 4)]))].sort();
  for (const [idSel, first] of [["y0", years[0]], ["y1", years[years.length - 1]]]) {
    $(idSel).append(...years.map((y) => el("option", { value: y, text: y, selected: y === first })));
    $(idSel).addEventListener("change", (e) => { S[idSel] = e.target.value; S.page = 0; draw(); });
  }
  const q = new URLSearchParams(location.search).get("q");
  if (q) { S.q = q; $("q").value = q; }
  $("q").addEventListener("input", (e) => { S.q = e.target.value; S.page = 0; draw(); });
  $("tier").addEventListener("change", (e) => { S.tier = e.target.value; S.page = 0; draw(); });
  $("status").addEventListener("change", (e) => { S.status = e.target.value; S.page = 0; draw(); });
  $("prev").addEventListener("click", () => { S.page--; drawTable(); window.scrollTo({ top: 0 }); });
  $("next").addEventListener("click", () => { S.page++; drawTable(); window.scrollTo({ top: 0 }); });
  $("download").addEventListener("click", () => {
    const cols = Object.keys(rows[0]);
    const out = view.map((e) => ({ ...e }));
    download("episodes_filtered.csv", toCSV(["volcano", ...cols], out.map((e) => ({ volcano: volcano.get(e.volcano_id).name, ...e }))));
  });
  onLang(() => { applyI18n(document); draw(); });
  draw();
}

main().catch((err) => showError($("table").parentNode, err));
