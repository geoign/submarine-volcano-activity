// Volcano page: facts, timeline, pass images, episodes, figures, records, zones.

import {
  CLASSES, RANK, DB, LANG, t, el, clear, add, renderChrome, loadJSON, loadCSV, onLang, onTheme, applyI18n, volcanoName,
  volcanoAlt, countryName, classLabel, classBadge, phenomena, fmtNum, fmtInt, fmtLatLon, dateRange, noteText,
  quicklookURL, showError,
} from "./common.js";
import { Timeline, ms, DAY } from "./timeline.js";

renderChrome("");

const id = new URLSearchParams(location.search).get("id") || "";
const wantEpisode = new URLSearchParams(location.search).get("ep") || "";
const $ = (x) => document.getElementById(x);
const S = { zone: "", showDismissed: false, listDismissed: false, selected: null };
let V, meta, zones, episodes, passes, lowres, periods, figures, ring, bands, chart, passByKey;

const siteOf = (z) => (z.endsWith("-LS") ? z.slice(0, -3) : z);
const stamp = (p) => p.time.slice(0, 4) + p.time.slice(5, 7) + p.time.slice(8, 10) + "T" + p.time.slice(11, 13) + p.time.slice(14, 16);
const obsId = (p) => `${p.zone_id}_${stamp(p)}_${p.sat}`;

function partialDate(s, end) {
  if (!s) return null;
  const [y, m, d] = s.split("-").map(Number);
  if (!end) return Date.UTC(y, (m || 1) - 1, d || 1);
  if (d) return Date.UTC(y, m - 1, d) + DAY;
  if (m) return Date.UTC(y, m, 1);
  return Date.UTC(y + 1, 0, 1);
}

async function load() {
  const [index, m, vols, zoneRows, eps, known] = await Promise.all([
    loadJSON(DB + "index.json"), loadJSON(DB + "meta.json"), loadCSV(DB + "volcanoes.csv"), loadCSV(DB + "zones.csv"),
    loadCSV(DB + "episodes.csv"), loadCSV(DB + "known_periods.csv"),
  ]);
  meta = m;
  V = vols.find((v) => v.volcano_id === id);
  if (!V) throw new Error(t("v.notfound"));
  zones = zoneRows.filter((z) => z.volcano_id === id);
  episodes = eps.filter((e) => e.volcano_id === id).map((e) => ({ ...e, t0: ms(e.start), t1: ms(e.end) }));
  const lastT = ms(meta.last_pass) + DAY;
  periods = known.filter((k) => k.volcano_id === id).map((k) => ({
    ...k, t0: partialDate(k.start, false),
    // No end date: the eruption was continuing when the catalogue was read, or its end is not on record.
    t1: partialDate(k.end, true) ?? (k.continuing === "yes" ? lastT : partialDate(k.start, true)),
  })).filter((k) => k.t0 !== null);
  const [pr, lr, fg, rw, ab] = await Promise.all([
    loadCSV(`${DB}passes/${id}.csv`, { optional: true }), loadCSV(`${DB}lowres/${id}.csv`, { optional: true }),
    loadCSV(DB + "figures.csv", { optional: true }), loadCSV(DB + "records/ring_waves.csv", { optional: true }),
    loadCSV(DB + "records/airborne_bands.csv", { optional: true }),
  ]);
  passes = pr.map((p) => ({
    ...p, t: ms(p.time), dw: Number(p.dw_km2 || 0), alert: p.level === "L2" || p.level === "L3", img: p.img === "1",
    site: siteOf(p.zone_id),
  }));
  passByKey = new Map(passes.map((p) => [obsId(p), p]));
  lowres = lr.map((d) => ({ ...d, t: ms(d.date), dw: Number(d.dw_km2 || 0), alert: d.level === "L2" || d.level === "L3" }));
  figures = fg.filter((f) => f.volcano_id === id);
  const zoneIds = new Set(zones.map((z) => z.zone_id));
  ring = rw.filter((r) => zoneIds.has(siteOf(r.zone_id)));
  bands = ab.filter((r) => zoneIds.has(siteOf(r.zone_id)));
}

// ------------------------------------------------------------------ head

function renderHead() {
  document.title = `${volcanoName(V)} · ${t("site.title")}`;
  const alt = volcanoAlt(V);
  const gvp = V.gvp_number ? el("a", { href: `https://volcano.si.edu/volcano.cfm?vn=${V.gvp_number}`, target: "_blank", rel: "noopener", text: V.gvp_number }) : "–";
  const sum = noteText(V, "summary");
  const active = CLASSES.filter((c) => c !== "nonvolcanic").reduce((n, c) => n + Number(V[`n_${c}`] || 0), 0);
  const total = CLASSES.reduce((n, c) => n + Number(V[`n_${c}`] || 0), 0);
  const tile = (label, value, sub) => el("div", { class: "tile" }, el("div", { class: "label", text: label }),
    el("div", { class: "value" }, value), sub ? el("div", { class: "sub", text: sub }) : null);
  add(clear($("head")),
    el("div", { class: "vhead" }, el("h1", { text: volcanoName(V) }), alt ? el("span", { class: "alt", text: alt }) : null,
      V.top_class ? classBadge(V.top_class) : null),
    el("div", { class: "facts" },
      el("span", {}, `${t("v.facts.country")}: `, el("b", { text: countryName(V.country) })),
      el("span", {}, `${t("v.facts.position")}: `, el("b", { text: fmtLatLon(V.lat, V.lon) })),
      el("span", {}, `${t("v.facts.gvp")}: `, el("b", {}, gvp)),
      el("span", {}, `${t("v.facts.depth")}: `, el("b", { text: t("depth." + V.depth_class) })),
      el("span", {}, `${t("v.facts.coverage")}: `, el("b", { text: t("coverage." + V.coverage) })),
      el("span", {}, `${t("v.facts.baseline")}: `, el("b", { text: t("baseline." + V.baseline_class) }))),
    sum.text ? el("p", { class: "summary", text: sum.text }) : null,
    el("div", { class: "tiles" },
      Number(V.n_passes) ? tile(t("v.tile.passes"), fmtInt(V.n_passes), t("v.tile.passes.sub", { usable: fmtInt(V.n_usable) })) : null,
      Number(V.n_passes) ? tile(t("v.tile.period"), dateRange(V.first_pass.slice(0, 7), V.last_pass.slice(0, 7))) : null,
      Number(V.lowres_days) ? tile(t("v.tile.lowres"), fmtInt(V.lowres_days), t("v.tile.lowres.sub")) : null,
      tile(t("v.tile.episodes"), fmtInt(total), t("v.tile.episodes.sub", { n: fmtInt(active) })),
      tile(t("v.tile.last"), V.last_activity || t("v.tile.none"), t("v.tile.last.sub"))));
}

// ------------------------------------------------------------------ timeline and viewer

function zonePasses() { return S.zone ? passes.filter((p) => p.site === S.zone) : passes; }
function viewable() { return zonePasses().filter((p) => p.img); }
function isShownAlert(p) {
  if (!p.alert) return false;
  const e = chart.byEpisode.get(p.episode_id);
  return S.showDismissed || !e || e.class !== "nonvolcanic";
}

function feedChart() {
  const zp = zonePasses();
  const eps = S.zone ? episodes.filter((e) => e.tier === "lowres" || e.zone_id === S.zone) : episodes;
  const all = [...passes.map((p) => p.t), ...lowres.map((d) => d.t), ...episodes.flatMap((e) => [e.t0, e.t1])];
  const d0 = Math.min(...all), d1 = Math.max(...all, ms(meta.last_pass));
  const pad = (d1 - d0) * 0.012 + 5 * DAY;
  chart.showDismissed = S.showDismissed;
  chart.setData({ passes: zp, lowres, episodes: eps, periods, domain: [d0 - pad, d1 + pad] });
}

function renderLegend() {
  const present = CLASSES.filter((c) => episodes.some((e) => e.class === c) && (c !== "nonvolcanic" || S.showDismissed));
  const item = (key, text) => el("span", {}, key, text);
  add(clear($("legend")),
    ...present.map((c) => item(el("i", { class: `dot ${c}` }), classLabel(c))),
    passes.length ? item(el("i", { class: "key-tick" }), t("v.legend.seen")) : null,
    passes.length ? item(el("i", { class: "key-tick", style: "opacity:.45;height:6px" }), t("v.legend.cloud")) : null,
    periods.length ? item(el("i", { class: "key-band" }), t("v.legend.eruption")) : null,
    lowres.length ? item(el("i", { class: "key-bar" }), t("v.legend.lowres")) : null);
}

function renderStrip() {
  const box = clear($("strip"));
  if (!chart.range) return;
  const [a, b] = chart.range;
  let list = viewable().filter((p) => p.t >= a && p.t <= b);
  const LIMIT = 80;
  if (list.length > LIMIT) {
    const alerts = list.filter(isShownAlert);
    if (alerts.length) list = alerts.slice(-LIMIT);
    else { const step = list.length / LIMIT; list = Array.from({ length: LIMIT }, (_, i) => list[Math.floor(i * step)]); }
  }
  if (S.selected && !list.includes(S.selected) && S.selected.t >= a && S.selected.t <= b) {
    list.push(S.selected);
    list.sort((x, y) => x.t - y.t);
  }
  for (const p of list) {
    const e = chart.byEpisode.get(p.episode_id);
    const cls = isShownAlert(p) ? (e ? e.class : "unreviewed") : null;
    const b2 = el("button", { type: "button", title: `${p.time.replace("T", " ")} UTC · ${p.sat}`, "aria-current": String(p === S.selected), onclick: () => select(p) },
      el("img", { loading: "lazy", alt: "", src: quicklookURL(meta.image_base, p), width: 116, height: 116 }),
      el("span", { class: "cap" }, p.time.slice(0, 10), cls ? el("i", { class: `dot ${cls}` }) : null));
    b2._pass = p;
    box.append(b2);
  }
  const cur = [...box.children].find((x) => x._pass === S.selected);
  if (cur) box.scrollLeft = cur.offsetLeft - box.clientWidth / 2 + 60;
}

function renderPass() {
  const p = S.selected, info = clear($("pass-info")), img = $("ql"), open = $("ql-open");
  if (!p) {
    img.hidden = true; open.hidden = true;
    info.append(el("p", { class: "notice", text: t("v.image.none") }));
    return;
  }
  const url = quicklookURL(meta.image_base, p);
  img.hidden = false;
  img.alt = `${volcanoName(V)} ${p.time} UTC ${p.sat}`;
  img.onerror = () => { img.hidden = true; info.prepend(el("p", { class: "error", text: t("v.image.missing") })); };
  img.src = url;
  open.hidden = false; open.href = url;
  const e = chart.byEpisode.get(p.episode_id);
  const row = (k, v) => (v === "" || v === null || v === undefined ? [] : [el("dt", { text: k }), el("dd", {}, v)]);
  const has = (x) => Number(x) > 0;
  info.append(el("dl", {},
    ...row(t("v.pass.time"), p.time.replace("T", " ")),
    ...row(t("v.pass.sat"), p.sat),
    ...row(t("v.pass.zone"), p.zone_id),
    ...row(t("v.pass.cls"), `${p.cls} · ${t("v.pass.cls." + p.cls)}`),
    ...row(t("v.pass.level"), p.level + (p.reasons ? ` · ${phenomena(p.reasons)}` : "")),
    ...row(t("v.pass.dw"), `${fmtNum(p.dw, 2)} km²` + (p.colour && p.colour !== "none" && has(p.dw) ? ` (${p.colour})` : "")),
    ...(has(p.dw) && p.dist_km !== "" ? row(t("v.pass.pos"), t("v.pass.pos.fmt", { d: p.dist_km, b: p.bearing })) : []),
    ...(has(p.fl_km2) ? row(t("v.pass.fl"), `${fmtNum(p.fl_km2, 2)} km²`) : []),
    ...(has(p.nl_km2) ? row(t("v.pass.nl"), `${fmtNum(p.nl_km2, 2)} km²`) : []),
    ...(has(p.th_px) ? row(t("v.pass.th"), p.th_px) : []),
    ...(has(p.ap_km2) ? row(t("v.pass.ap"), `${fmtNum(p.ap_km2, 2)} km²`) : []),
    ...(e ? row(t("v.pass.episode"), el("a", { href: `#ep-${e.episode_id}` }, classBadge(e.class, true))) : [])));
}

function select(p, opts) {
  S.selected = p;
  chart.select(p, opts);
  renderPass();
  renderStrip();
}

function step(dir, alertsOnly) {
  const list = viewable().filter((p) => !alertsOnly || isShownAlert(p));
  if (!list.length) return;
  const cur = S.selected ? S.selected.t : (dir > 0 ? -Infinity : Infinity);
  const next = dir > 0 ? list.find((p) => p.t > cur) : [...list].reverse().find((p) => p.t < cur);
  if (next) select(next, { reveal: true });
}

function setupTimeline() {
  if (!passes.length && !lowres.length && !episodes.length) return;
  $("timeline-section").hidden = false;
  chart = new Timeline($("chart"), $("tip"), { onSelect: (p) => select(p), onRange: () => queueStrip() });
  const hi = zones.filter((z) => z.tier === "highres");
  const sel = $("zone");
  if (hi.length > 1) {
    sel.append(el("option", { value: "", text: t("v.zone.all") }), ...hi.map((z) => el("option", { value: z.zone_id, text: `${z.zone_id} · ${z.name}` })));
    sel.addEventListener("change", () => { S.zone = sel.value; feedChart(); renderStrip(); });
  } else $("zone-label").hidden = true;
  $("dismissed").addEventListener("change", (e) => { S.showDismissed = e.target.checked; feedChart(); renderLegend(); renderStrip(); });
  $("range").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-range]");
    if (!b) return;
    const [d0, d1] = chart.domain;
    if (b.dataset.range === "all") chart.setRange(d0, d1);
    else { const end = S.selected ? Math.min(d1, S.selected.t + Number(b.dataset.range) * 182 * DAY) : d1; chart.setRange(end - Number(b.dataset.range) * 365 * DAY, end); }
  });
  $("zoom-in").addEventListener("click", () => chart.zoom(0.6, S.selected && S.selected.t > chart.range[0] && S.selected.t < chart.range[1] ? S.selected.t : undefined));
  $("zoom-out").addEventListener("click", () => chart.zoom(1 / 0.6));
  $("prev").addEventListener("click", () => step(-1, false));
  $("next").addEventListener("click", () => step(1, false));
  $("prev-alert").addEventListener("click", () => step(-1, true));
  $("next-alert").addEventListener("click", () => step(1, true));
  $("chart").addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") { step(-1, e.shiftKey); e.preventDefault(); }
    else if (e.key === "ArrowRight") { step(1, e.shiftKey); e.preventDefault(); }
    else if (e.key === "+" || e.key === "=") chart.zoom(0.6);
    else if (e.key === "-") chart.zoom(1 / 0.6);
  });
  feedChart();
  renderLegend();
  if (passes.some((p) => p.img)) $("viewer-section").hidden = false;

  // What to show first: the episode asked for, else the latest significant one.
  const order = (e) => [RANK[e.class] <= 2 ? 0 : e.class === "nonvolcanic" ? 2 : 1, -e.t1];
  const pick = episodes.find((e) => e.episode_id === wantEpisode)
    || [...episodes].sort((a, b) => order(a)[0] - order(b)[0] || order(a)[1] - order(b)[1])[0];
  if (wantEpisode && pick) showEpisode(pick, false);
  else {
    const p = pick && passByKey.get(pick.peak);
    if (p && p.img) select(p); else { const v = viewable(); if (v.length) select(v[v.length - 1]); else renderStrip(); }
  }
}

let stripTimer = 0;
function queueStrip() { clearTimeout(stripTimer); stripTimer = setTimeout(renderStrip, 150); }

function showEpisode(e, scroll = true) {
  let refeed = false;
  if (e.class === "nonvolcanic" && !S.showDismissed) { S.showDismissed = true; $("dismissed").checked = true; refeed = true; }
  // An episode of another zone than the one chosen: back to all zones, or its passes would not be drawn.
  if (S.zone && e.tier === "highres" && e.zone_id !== S.zone) { S.zone = ""; $("zone").value = ""; refeed = true; }
  if (refeed) { feedChart(); renderLegend(); }
  const pad = Math.max(60 * DAY, (e.t1 - e.t0) * 0.6);
  chart.setRange(e.t0 - pad, e.t1 + pad + DAY);
  const p = passByKey.get(e.peak);
  if (p && p.img) select(p);
  if (scroll) $("timeline-section").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ------------------------------------------------------------------ episodes

function renderEpisodes() {
  if (!episodes.length) return;
  $("episodes-section").hidden = false;
  const dismissed = episodes.filter((e) => e.class === "nonvolcanic").length;
  const btn = $("toggle-dismissed");
  btn.hidden = !dismissed;
  btn.textContent = S.listDismissed ? t("v.episodes.hideDismissed") : t("v.episodes.showDismissed", { n: dismissed });
  btn.onclick = () => { S.listDismissed = !S.listDismissed; renderEpisodes(); };
  const box = clear($("episodes"));
  const list = episodes.filter((e) => S.listDismissed || e.class !== "nonvolcanic" || e.episode_id === wantEpisode)
    .sort((a, b) => b.t0 - a.t0);
  if (!list.length) box.append(el("p", { class: "notice", text: t("v.episodes.none") }));
  for (const e of list) {
    const note = noteText(e, "note"), owner = noteText(e, "owner"), cur = noteText(e, "curation");
    const low = e.tier === "lowres";
    const extra = (label, value) => (value ? el("p", { class: "extra" }, el("b", { text: label + ": " }), value) : null);
    box.append(el("article", { class: `episode ${e.class}`, id: `ep-${e.episode_id}` },
      el("div", { class: "top" },
        el("span", { class: "dates", text: dateRange(e.start, e.end) }), classBadge(e.class),
        el("span", { class: "tag", text: t("tier." + e.tier) }),
        el("span", { class: "nums", text: [
          phenomena(e.phenomena), e.max_dw_km2 && Number(e.max_dw_km2) > 0 ? t("v.ep.maxdw", { v: fmtNum(e.max_dw_km2, 2) }) : "",
          t(low ? "v.ep.days" : "v.ep.passes", { a: e.n_detect, u: e.n_seen }), e.sensors, low ? "" : e.zone_id,
        ].filter(Boolean).join(" · ") })),
      note.text ? el("p", { class: "note", lang: note.fallback ? (LANG === "ja" ? "en" : "ja") : null, text: note.text }) : null,
      extra(t("v.ep.cause"), e.class === "nonvolcanic" && e.cause ? t("cause." + e.cause) : ""),
      extra(t("v.ep.known"), e.known_ref),
      extra(t("v.ep.owner"), owner.text),
      extra(t("v.ep.prior"), e.prior_reports),
      extra(t("v.ep.curation"), cur.text),
      extra(t("v.ep.basis"), e.basis ? t("basis." + e.basis) : ""),
      el("div", { class: "actions" },
        el("button", { type: "button", class: "btn", text: t("v.ep.show"), onclick: () => showEpisode(e) }),
        e.image ? el("a", { class: "btn", href: `${meta.image_base}/${e.image}`, target: "_blank", rel: "noopener", text: t("v.ep.sheet") }) : null)));
  }
}

// ------------------------------------------------------------------ figures, records, zones

function renderFigures() {
  if (!figures.length) return;
  $("figures-section").hidden = false;
  clear($("figures")).append(...figures.map((f) => {
    const url = `${meta.image_base}/${f.file}`;
    return el("figure", {}, el("a", { href: url, target: "_blank", rel: "noopener" }, el("img", { loading: "lazy", src: url, alt: "" })),
      el("figcaption", { text: noteText(f, "caption").text }));
  }));
}

function simpleTable(table, head, rows) {
  clear(table).append(el("thead", {}, el("tr", {}, ...head.map((h) => el("th", { text: h })))),
    el("tbody", {}, ...rows.map((r) => el("tr", {}, ...r.map((c) => el("td", {}, c))))));
}

function renderRecords() {
  const box = clear($("records"));
  if (!ring.length && !bands.length) return;
  $("records-section").hidden = false;
  if (ring.length) {
    const tb = el("table", { class: "data" });
    simpleTable(tb, ["Pass (UTC)", "Zone", "Centre (km E, N)", "Reach", "Spacing", "Sea", "With it", "Noted"],
      ring.map((r) => [r.pass_utc, r.zone_id, r.centre, r.reach, r.spacing, r.sea, r.with_it, r.noted]));
    box.append(el("h3", { text: t("v.records.ring") }), el("div", { class: "table-wrap" }, tb));
  }
  if (bands.length) {
    const tb = el("table", { class: "data" });
    simpleTable(tb, ["Day", "UTC", "Zone", "Sensor", "Area km²", "Length km", "From Jadid Island (km, bearing)", "Level"],
      bands.map((r) => [r.day, r.utc, r.zone_id, r.sensor, r.area_km2, r.length_km, r.from_jadid, r.level]));
    box.append(el("h3", { text: t("v.records.bands") }), el("div", { class: "table-wrap" }, tb));
  }
}

function renderZones() {
  $("zones-section").hidden = false;
  simpleTable($("zones"), ["v.zones.id", "v.zones.name", "v.zones.kind", "v.zones.centre", "v.zones.radius", "v.zones.sensors"].map((k) => t(k)),
    zones.map((z) => [z.zone_id, z.name, z.tier === "lowres" ? t("tier.lowres") : z.kind, fmtLatLon(z.lat, z.lon), `${z.radius_km} km`,
      z.tier === "lowres" ? "OLCI, VIIRS" : z.sensors]));
  const gvp = periods.filter((k) => k.source);
  $("known-title").hidden = $("known-wrap").hidden = !gvp.length;
  if (gvp.length) {
    simpleTable($("known"), ["Source", "Kind", "Start", "End", "Area"],
      gvp.map((k) => [k.source === "GVP" ? "Smithsonian GVP" : "This database", k.kind, k.start,
        k.end || (k.continuing === "yes" ? "(continuing)" : "–"), k.area]));
  }
  const links = clear($("data-links"));
  const link = (href, text) => { if (links.childNodes.length) links.append(" · "); links.append(el("a", { href, text })); };
  if (passes.length) link(`${DB}passes/${id}.csv`, t("v.data.passes"));
  if (lowres.length) link(`${DB}lowres/${id}.csv`, t("v.data.lowres"));
  link(`${DB}episodes.csv`, t("v.data.episodes"));
  if (V.gvp_number) link(`https://volcano.si.edu/volcano.cfm?vn=${V.gvp_number}`, t("v.data.gvp"));
}

function renderAll() {
  applyI18n(document);
  renderHead();
  renderEpisodes();
  renderFigures();
  renderRecords();
  renderZones();
  if (chart) { renderLegend(); renderPass(); chart.draw(); const z = $("zone").options[0]; if (z) z.textContent = t("v.zone.all"); }
}

load().then(() => {
  renderAll();
  setupTimeline();
  onLang(renderAll);
  onTheme(() => chart && chart.draw());
  if (wantEpisode) { const n = document.getElementById(`ep-${wantEpisode}`); if (n) n.classList.add("target"); }
}).catch((err) => showError($("head"), err));
