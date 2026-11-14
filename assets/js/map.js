// Map page: every volcano as a point, coloured by the most significant class of its episodes
// in the chosen period; a list beside it.

import {
  CLASSES, DB, t, el, clear, renderChrome, loadJSON, onLang, onTheme, cssVar, volcanoName, volcanoAlt,
  countryName, classLabel, classBadge, showError,
} from "./common.js";

renderChrome("map");

const L = window.L;
// The map runs from 35°W eastwards to 325°E so that the Pacific is whole and the cut lies in the Atlantic.
const WEST = -35;
const RADIUS = [7.5, 7, 6.5, 5.5, 5.5, 4.5, 4, 4.5];
const MAP_CLASSES = CLASSES.filter((c) => c !== "nonvolcanic");
const state = { period: "all", search: "", shown: new Set(MAP_CLASSES.filter((c) => c !== "unreviewed")) };
let index, meta, map, markers = [], landLayers = [];

const shiftLon = (lon) => (lon < WEST ? lon + 360 : lon);

function periodStart() {
  if (state.period === "all") return "0000";
  const d = new Date(meta.last_pass + "T00:00:00Z");
  d.setUTCFullYear(d.getUTCFullYear() - (state.period === "5y" ? 5 : 1));
  return d.toISOString().slice(0, 10);
}

/** Episodes of a volcano that fall in the period and belong to a shown class. */
function summarise(v) {
  const from = periodStart();
  const counts = new Array(CLASSES.length).fill(0);
  let top = -1, last = "";
  for (const [start, end, rank] of v.episodes) {
    if (end < from || !state.shown.has(CLASSES[rank])) continue;
    counts[rank]++;
    if (top < 0 || rank < top) top = rank;
    if (end > last) last = end;
  }
  return { counts, top, last, n: counts.reduce((a, b) => a + b, 0) };
}

function matches(v) {
  const q = state.search.trim().toLowerCase();
  if (!q) return true;
  return [v.name, v.name_ja, v.country, countryName(v.country), v.id, v.gvp].some((s) => (s || "").toLowerCase().includes(q));
}

function popupContent(v, s) {
  const box = el("div", { class: "popup" },
    el("h3", { text: volcanoName(v) }),
    el("div", { class: "meta", text: [volcanoAlt(v), countryName(v.country)].filter(Boolean).join(" · ") }));
  if (s.n) {
    box.append(el("ul", {}, ...CLASSES.map((c, i) => s.counts[i]
      ? el("li", {}, el("i", { class: `dot ${c}` }), `${classLabel(c)}: ${s.counts[i]}`) : null)));
  } else {
    box.append(el("p", { class: "meta", text: t("map.noepisode") }));
  }
  box.append(el("a", { href: `volcano.html?id=${encodeURIComponent(v.id)}`, text: t("map.open") }));
  return box;
}

function drawLand(polys) {
  for (const layer of landLayers) layer.remove();
  landLayers = [];
  const style = { stroke: false, fillColor: cssVar("--land"), fillOpacity: 1, interactive: false };
  for (const shift of [0, 360]) {
    const rings = polys.map((poly) => poly.map((ring) => ring.map(([x, y]) => [y, x + shift])));
    landLayers.push(L.polygon(rings, style).addTo(map));
  }
  const lines = [];
  for (let lon = WEST + 5; lon <= WEST + 360; lon += 30) lines.push([[-80, lon], [80, lon]]);
  for (let lat = -60; lat <= 60; lat += 30) lines.push([[lat, WEST], [lat, WEST + 360]]);
  landLayers.push(L.polyline(lines, { color: cssVar("--graticule"), weight: 1, interactive: false }).addTo(map));
  landLayers.forEach((l) => l.bringToBack());
}

function drawMarkers() {
  for (const m of markers) m.remove();
  markers = [];
  const surface = cssVar("--surface");
  const rows = index.volcanoes.map((v) => ({ v, s: summarise(v) }));
  // Least significant first, so that the significant ones lie on top.
  rows.sort((a, b) => (b.s.top < 0 ? 99 : b.s.top) - (a.s.top < 0 ? 99 : a.s.top));
  for (const { v, s } of rows) {
    const hit = matches(v);
    const cls = s.top >= 0 ? CLASSES[s.top] : null;
    const opt = cls
      ? { radius: RADIUS[s.top], fillColor: cssVar(`--c-${cls}`), fillOpacity: 1, color: cls === "unreviewed" ? cssVar("--muted") : surface, weight: 2 }
      : { radius: 3, fillColor: surface, fillOpacity: 0.9, color: cssVar("--muted"), weight: 1 };
    if (!hit) Object.assign(opt, { fillOpacity: 0.12, opacity: 0.2 });
    const m = L.circleMarker([v.lat, shiftLon(v.lon)], opt).addTo(map);
    // A node, not a string: Leaflet would insert a string as HTML.
    m.bindTooltip(() => el("span", { text: `${volcanoName(v)} · ${cls ? classLabel(cls, true) : t("class.none")}` }), { direction: "top", offset: [0, -4] });
    m.bindPopup(() => popupContent(v, summarise(v)), { maxWidth: 280 });
    markers.push(m);
  }
}

function drawList() {
  const box = clear(document.getElementById("list"));
  const q = state.search.trim();
  let rows = index.volcanoes.map((v) => ({ v, s: summarise(v) })).filter(({ v }) => matches(v));
  const withEpisodes = rows.filter((r) => r.s.n);
  if (!q) rows = withEpisodes;
  rows.sort((a, b) => (a.s.top < 0 ? 99 : a.s.top) - (b.s.top < 0 ? 99 : b.s.top) || (b.s.last > a.s.last ? 1 : b.s.last < a.s.last ? -1 : 0)
    || a.v.name.localeCompare(b.v.name));
  box.append(el("div", { class: "vlist-head", text: t("map.list.head", { n: withEpisodes.length, total: index.volcanoes.length }) }));
  if (!rows.length) box.append(el("p", { class: "notice", style: "padding:.6rem .8rem", text: t("map.list.empty") }));
  for (const { v, s } of rows) {
    const cls = s.top >= 0 ? CLASSES[s.top] : null;
    const alt = volcanoAlt(v);
    box.append(el("a", { class: "row", href: `volcano.html?id=${encodeURIComponent(v.id)}` },
      el("i", { class: `dot ${cls || "none"}` }),
      el("span", {},
        el("span", { class: "name", text: volcanoName(v) }), alt ? el("span", { class: "meta", text: " " + alt }) : null,
        el("div", { class: "meta", text: countryName(v.country) + (s.n ? ` · ${classLabel(cls, true)} · ${s.n === 1 ? t("map.count.episode1") : t("map.count.episodes", { n: s.n })}` : "") })),
      el("span", { class: "when", text: s.last ? s.last.slice(0, 7) : "" })));
  }
}

function drawChips() {
  const box = clear(document.getElementById("classes"));
  for (const c of MAP_CLASSES) {
    box.append(el("button", {
      type: "button", class: "chip", "aria-pressed": String(state.shown.has(c)),
      onclick: () => { state.shown.has(c) ? state.shown.delete(c) : state.shown.add(c); redraw(); },
    }, el("i", { class: `dot ${c}` }), classLabel(c)));
  }
}

function redraw() { drawChips(); drawMarkers(); drawList(); }

async function main() {
  [index, meta] = await Promise.all([loadJSON(DB + "index.json"), loadJSON(DB + "meta.json")]);
  const land = await loadJSON("assets/land.json");
  map = L.map("map", {
    renderer: L.canvas({ tolerance: 8, padding: 0.5 }), zoomSnap: 0.25, zoomDelta: 0.5, maxZoom: 9,
    maxBounds: [[-82, WEST], [82, WEST + 360]], maxBoundsViscosity: 1, attributionControl: true, worldCopyJump: false,
  });
  map.attributionControl.setPrefix(false).addAttribution(t("map.attrib"));
  const fit = () => map.setMinZoom(Math.max(0.5, Math.log2(map.getSize().x / 256) - 0.02));
  map.setView([8, 150], 2);
  fit();
  if (map.getZoom() < map.getMinZoom()) map.setZoom(map.getMinZoom());
  map.on("resize", fit);
  drawLand(land);
  redraw();

  document.getElementById("period").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-period]");
    if (!b) return;
    state.period = b.dataset.period;
    for (const x of b.parentNode.children) x.setAttribute("aria-pressed", String(x === b));
    redraw();
  });
  document.getElementById("search").addEventListener("input", (e) => { state.search = e.target.value; drawMarkers(); drawList(); });
  onLang(redraw);
  onTheme(() => { drawLand(land); drawMarkers(); });
}

main().catch((err) => showError(document.getElementById("list"), err));
