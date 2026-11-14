// Timeline of one volcano on a canvas: episodes, high-resolution passes, low-resolution days.
// Each panel has its own single y scale; the x axis (time) is shared.

import { cssVar, t, classLabel, fmtNum, phenomena, RANK } from "./common.js";

const DAY = 86400000;
const M = { left: 52, right: 14, top: 8 };
const H = { episodes: 34, hires: 168, rugs: 22, lowres: 78, axis: 22, gap: 10 };

const ms = (s) => Date.parse(s.length <= 10 ? s + "T00:00:00Z" : s + ":00Z");
const niceTicks = (max) => {
  const all = [0.5, 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500];
  const out = all.filter((v) => v <= max);
  while (out.length > 4) out.splice(out.length % 2 ? 0 : 1, 1);
  return out;
};

export class Timeline {
  constructor(canvas, tooltip, { onSelect, onRange }) {
    this.canvas = canvas;
    this.tooltip = tooltip;
    this.onSelect = onSelect;
    this.onRange = onRange || (() => {});
    this.passes = [];
    this.lowres = [];
    this.episodes = [];
    this.periods = [];
    this.showDismissed = false;
    this.selected = null;
    this.hover = null;
    this.pointers = new Map();
    this.bind();
    new ResizeObserver(() => this.draw()).observe(canvas.parentNode);
  }

  setData({ passes, lowres, episodes, periods, domain }) {
    this.passes = passes;
    this.lowres = lowres;
    this.episodes = episodes;
    this.periods = periods;
    this.byEpisode = new Map(episodes.map((e) => [e.episode_id, e]));
    this.usable = passes.filter((p) => p.cls !== "C");
    this.domain = domain;
    if (!this.range) this.range = domain.slice();
    const alertMax = Math.max(1, ...passes.filter((p) => p.alert).map((p) => p.dw));
    this.hiMax = alertMax * 1.08;
    this.loMax = Math.max(1, ...lowres.filter((d) => d.alert).map((d) => d.dw)) * 1.08;
    this.draw();
  }

  setRange(a, b) {
    const [d0, d1] = this.domain;
    const span = Math.min(Math.max(b - a, 20 * DAY), d1 - d0);
    a = Math.min(Math.max(a, d0), d1 - span);
    this.range = [a, a + span];
    this.onRange(this.range);
    this.draw();
  }

  zoom(factor, centre) {
    const [a, b] = this.range;
    const c = centre ?? (a + b) / 2;
    this.setRange(c - (c - a) * factor, c + (b - c) * factor);
  }

  select(pass, { reveal = false } = {}) {
    this.selected = pass;
    if (pass && reveal && (pass.t < this.range[0] || pass.t > this.range[1])) {
      const span = this.range[1] - this.range[0];
      this.setRange(pass.t - span / 2, pass.t + span / 2);
    } else this.draw();
  }

  visible(p) {
    if (!p.alert) return true;
    const e = this.byEpisode.get(p.episode_id);
    return this.showDismissed || !e || e.class !== "nonvolcanic";
  }

  // ------------------------------------------------------------------ geometry

  layout() {
    const w = this.canvas.clientWidth;
    const hasHi = this.passes.length > 0, hasLo = this.lowres.length > 0;
    let y = M.top;
    const L = { w, x0: M.left, x1: w - M.right };
    L.episodes = [y, y + H.episodes]; y += H.episodes + H.gap;
    if (hasHi) { L.hires = [y, y + H.hires]; y += H.hires; L.rugs = [y + 3, y + H.rugs]; y += H.rugs + H.gap; }
    if (hasLo) { L.lowres = [y, y + H.lowres]; y += H.lowres + H.gap; }
    L.axis = y - H.gap + 4;
    L.height = L.axis + H.axis;
    return L;
  }

  x(tm, L) { return L.x0 + (tm - this.range[0]) / (this.range[1] - this.range[0]) * (L.x1 - L.x0); }
  time(px, L) { return this.range[0] + (px - L.x0) / (L.x1 - L.x0) * (this.range[1] - this.range[0]); }
  yHi(v, L) { return L.hires[1] - 4 - Math.sqrt(Math.max(v, 0) / this.hiMax) * (L.hires[1] - L.hires[0] - 14); }
  yLo(v, L) { return L.lowres[1] - 8 - Math.sqrt(Math.max(v, 0) / this.loMax) * (L.lowres[1] - L.lowres[0] - 18); }

  // ------------------------------------------------------------------ drawing

  draw() {
    if (!this.domain) return;
    const L = this.L = this.layout();
    const dpr = window.devicePixelRatio || 1;
    const c = this.canvas;
    c.style.height = L.height + "px";
    if (c.width !== Math.round(L.w * dpr) || c.height !== Math.round(L.height * dpr)) {
      c.width = Math.round(L.w * dpr);
      c.height = Math.round(L.height * dpr);
    }
    const g = c.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, L.w, L.height);
    const col = {
      ink: cssVar("--ink"), ink2: cssVar("--ink-2"), muted: cssVar("--muted"), grid: cssVar("--grid"), axis: cssVar("--axis"),
      surface: cssVar("--surface"), band: cssVar("--eruption-band"), lowres: cssVar("--c-lowres"), accent: cssVar("--accent"),
    };
    const cls = (name) => cssVar(`--c-${name}`);
    g.font = "11px system-ui, sans-serif";
    g.textBaseline = "middle";
    const [r0, r1] = this.range;
    const bottom = L.axis;

    // time grid: years, or months when zoomed in
    const spanDays = (r1 - r0) / DAY;
    g.strokeStyle = col.grid; g.fillStyle = col.muted; g.lineWidth = 1; g.textAlign = "center";
    const d = new Date(r0);
    const byMonth = spanDays < 900;
    const step = byMonth ? (spanDays < 200 ? 1 : 3) : (spanDays > 3650 * 1.6 ? 2 : 1);
    let cur = byMonth ? Date.UTC(d.getUTCFullYear(), Math.floor(d.getUTCMonth() / step) * step, 1) : Date.UTC(d.getUTCFullYear(), 0, 1);
    for (let guard = 0; cur <= r1 && guard < 400; guard++) {
      const dd = new Date(cur);
      if (cur >= r0) {
        const px = Math.round(this.x(cur, L)) + 0.5;
        g.beginPath(); g.moveTo(px, M.top); g.lineTo(px, bottom); g.stroke();
        const label = byMonth
          ? (dd.getUTCMonth() === 0 || guard === 0 || spanDays < 200 ? `${dd.getUTCFullYear()}-${String(dd.getUTCMonth() + 1).padStart(2, "0")}` : String(dd.getUTCMonth() + 1).padStart(2, "0"))
          : String(dd.getUTCFullYear());
        g.fillText(label, px, bottom + 11);
      }
      cur = byMonth ? Date.UTC(dd.getUTCFullYear(), dd.getUTCMonth() + step, 1) : Date.UTC(dd.getUTCFullYear() + step, 0, 1);
    }

    // documented eruption periods, behind everything
    g.save();
    g.beginPath(); g.rect(L.x0, M.top, L.x1 - L.x0, bottom - M.top); g.clip();
    for (const p of this.periods) {
      const a = Math.max(this.x(p.t0, L), L.x0 - 2), b = Math.min(this.x(p.t1, L), L.x1 + 2);
      if (b < L.x0 || a > L.x1) continue;
      g.fillStyle = col.band;
      g.fillRect(a, M.top, Math.max(b - a, 2), bottom - M.top);
      g.fillStyle = cls("known");
      g.fillRect(a, M.top, 1.5, bottom - M.top);
    }
    g.restore();

    // panel labels
    g.textAlign = "left"; g.fillStyle = col.ink2;
    const label = (text, y) => { g.save(); g.font = "600 11px system-ui, sans-serif"; g.fillStyle = col.ink2; g.fillText(text, L.x0 + 6, y); g.restore(); };

    // episodes: one row per tier
    g.save();
    g.beginPath(); g.rect(L.x0, L.episodes[0], L.x1 - L.x0, H.episodes); g.clip();
    const rows = { highres: L.episodes[0] + 9, lowres: L.episodes[0] + 25 };
    const eps = this.episodes.filter((e) => this.showDismissed || e.class !== "nonvolcanic")
      .sort((a, b) => RANK[b.class] - RANK[a.class]);
    for (const e of eps) {
      const a = this.x(e.t0, L), b = this.x(e.t1 + DAY, L);
      if (b < L.x0 - 4 || a > L.x1 + 4) continue;
      const wdt = Math.max(b - a, 4), y = rows[e.tier];
      g.fillStyle = e.class === "unreviewed" ? col.surface : cls(e.class);
      g.beginPath(); g.roundRect(a, y - 4, wdt, 8, 3); g.fill();
      if (e.class === "unreviewed") { g.strokeStyle = col.muted; g.lineWidth = 1.5; g.stroke(); }
    }
    g.restore();
    g.fillStyle = col.muted; g.textAlign = "right"; g.font = "10px system-ui, sans-serif";
    g.fillText(t("v.axis.hrShort"), L.x0 - 6, rows.highres);
    g.fillText(t("v.axis.lrShort"), L.x0 - 6, rows.lowres);
    g.textAlign = "left"; g.font = "11px system-ui, sans-serif";

    // high-resolution passes
    if (L.hires) {
      g.strokeStyle = col.axis; g.lineWidth = 1;
      const base = Math.round(this.yHi(0, L)) + 0.5;
      g.beginPath(); g.moveTo(L.x0, base); g.lineTo(L.x1, base); g.stroke();
      g.textAlign = "right"; g.fillStyle = col.muted;
      g.fillText("0", L.x0 - 6, base);
      for (const v of niceTicks(this.hiMax)) {
        const y = Math.round(this.yHi(v, L)) + 0.5;
        g.strokeStyle = col.grid; g.beginPath(); g.moveTo(L.x0, y); g.lineTo(L.x1, y); g.stroke();
        g.fillText(String(v), L.x0 - 6, y);
      }
      g.textAlign = "left";
      g.save();
      g.beginPath(); g.rect(L.x0 - 6, L.hires[0] - 6, L.x1 - L.x0 + 12, L.rugs[1] - L.hires[0] + 8); g.clip();
      // rugs: sea visible without alert, sea not visible
      const seenY = L.rugs[0] + 1, cloudY = L.rugs[0] + 12;
      for (const p of this.passes) {
        if (p.t < r0 - DAY || p.t > r1 + DAY) continue;
        const px = Math.round(this.x(p.t, L)) + 0.5;
        if (p.cls === "C") { g.strokeStyle = col.axis; g.beginPath(); g.moveTo(px, cloudY); g.lineTo(px, cloudY + 5); g.stroke(); }
        else if (!p.alert || !this.visible(p)) { g.strokeStyle = col.muted; g.beginPath(); g.moveTo(px, seenY); g.lineTo(px, seenY + 8); g.stroke(); }
      }
      // alert passes; significant classes last so that they lie on top
      const alerts = this.passes.filter((p) => p.alert && this.visible(p) && p.t >= r0 - DAY && p.t <= r1 + DAY);
      const classOf = (p) => (this.byEpisode.get(p.episode_id) || {}).class || "unreviewed";
      alerts.sort((a, b) => RANK[classOf(b)] - RANK[classOf(a)]);
      for (const p of alerts) {
        const k = classOf(p), px = this.x(p.t, L), py = this.yHi(p.dw, L);
        const r = k === "nonvolcanic" ? 3 : 4.5;
        g.beginPath(); g.arc(px, py, r + 2, 0, 7); g.fillStyle = col.surface; g.fill();     // surface ring
        g.beginPath(); g.arc(px, py, r, 0, 7);
        if (k === "unreviewed") { g.strokeStyle = col.muted; g.lineWidth = 1.5; g.stroke(); g.lineWidth = 1; }
        else { g.fillStyle = cls(k); g.fill(); }
      }
      g.restore();
      label(`${t("v.axis.hires")} · ${t("v.axis.dw")}`, L.hires[0] + 4);
    }

    // low-resolution days
    if (L.lowres) {
      const base = Math.round(this.yLo(0, L)) + 0.5;
      g.strokeStyle = col.axis; g.beginPath(); g.moveTo(L.x0, base); g.lineTo(L.x1, base); g.stroke();
      g.textAlign = "right"; g.fillStyle = col.muted;
      g.fillText("0", L.x0 - 6, base);
      for (const v of niceTicks(this.loMax).slice(-2)) {
        const y = Math.round(this.yLo(v, L)) + 0.5;
        g.strokeStyle = col.grid; g.beginPath(); g.moveTo(L.x0, y); g.lineTo(L.x1, y); g.stroke();
        g.fillText(String(v), L.x0 - 6, y);
      }
      g.textAlign = "left";
      g.save();
      g.beginPath(); g.rect(L.x0, L.lowres[0], L.x1 - L.x0, H.lowres); g.clip();
      for (const dday of this.lowres) {
        if (dday.t < r0 - DAY || dday.t > r1 + DAY) continue;
        const px = Math.round(this.x(dday.t, L)) + 0.5;
        if (dday.alert) {
          g.strokeStyle = col.lowres; g.lineWidth = spanDays < 400 ? 2 : 1;
          g.beginPath(); g.moveTo(px, base); g.lineTo(px, this.yLo(dday.dw, L)); g.stroke(); g.lineWidth = 1;
        } else { g.strokeStyle = col.axis; g.beginPath(); g.moveTo(px, base + 2); g.lineTo(px, base + 6); g.stroke(); }
      }
      g.restore();
      label(`${t("v.axis.lowres")} · ${t("v.axis.dw")}`, L.lowres[0] + 4);
    }

    // selection and hover
    const mark = (p, colour, widthPx) => {
      if (!p || p.t < r0 || p.t > r1) return;
      const px = Math.round(this.x(p.t, L)) + 0.5;
      g.strokeStyle = colour; g.lineWidth = widthPx;
      g.beginPath(); g.moveTo(px, M.top); g.lineTo(px, bottom); g.stroke(); g.lineWidth = 1;
    };
    mark(this.selected, col.accent, 2);
    if (this.hover) mark(this.hover.item, col.muted, 1);
  }

  // ------------------------------------------------------------------ interaction

  nearest(px, py) {
    const L = this.L;
    if (!L || px < L.x0 - 8 || px > L.x1 + 8) return null;
    const inLow = L.lowres && py >= L.lowres[0] && (!L.hires || py > L.rugs[1] + 4);
    const pool = inLow ? this.lowres : this.usable;
    let best = null, bestD = 14;
    // Alerts win over quiet passes at the same distance: the reader aims at the dots.
    for (const item of pool) {
      if (item.t < this.range[0] - DAY || item.t > this.range[1] + DAY) continue;
      const dx = Math.abs(this.x(item.t, L) - px);
      const dAdj = dx - (item.alert && (inLow || this.visible(item)) ? 3 : 0);
      if (dAdj < bestD) { bestD = dAdj; best = item; }
    }
    return best ? { item: best, lowres: inLow } : null;
  }

  showTooltip(hit, px) {
    const tip = this.tooltip;
    if (!hit) { tip.hidden = true; return; }
    while (tip.firstChild) tip.removeChild(tip.firstChild);
    const line = (k, v) => {
      const div = document.createElement("div");
      const b = document.createElement("span"); b.className = "v"; b.textContent = v;
      div.append(b);
      if (k) { const s = document.createElement("span"); s.className = "k"; s.textContent = " " + k; div.append(s); }
      tip.append(div);
    };
    const it = hit.item;
    if (hit.lowres) {
      line(`${it.src.toUpperCase()} · ${t("tier.lowres")}`, it.date);
      line(t("v.pass.dw"), `${fmtNum(it.dw, 2)} km²`);
      line(t("v.pass.level"), it.level);
    } else {
      line(`UTC · ${it.sat} · ${it.zone_id}`, it.time.replace("T", " "));
      if (it.alert) {
        const e = this.byEpisode.get(it.episode_id);
        line(phenomena(it.reasons), it.level);
        if (e) line("", classLabel(e.class));
      }
      line(t("v.pass.dw"), `${fmtNum(it.dw, 2)} km²`);
    }
    tip.hidden = false;
    const w = tip.offsetWidth, cw = this.canvas.clientWidth;
    tip.style.left = Math.min(Math.max(px + 14, 4), cw - w - 4) + "px";
    tip.style.top = (this.canvas.offsetTop + 30) + "px";
  }

  bind() {
    const c = this.canvas;
    const pos = (e) => { const r = c.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    c.addEventListener("pointerdown", (e) => {
      c.setPointerCapture(e.pointerId);
      const [x, y] = pos(e);
      this.pointers.set(e.pointerId, { x, y, x0: x, y0: y });
      this.drag = { range: this.range.slice(), moved: false };
      if (this.pointers.size === 2) {
        const [a, b] = [...this.pointers.values()];
        this.pinch = { dist: Math.abs(a.x - b.x) || 1, range: this.range.slice(), centre: this.time((a.x + b.x) / 2, this.L) };
      }
    });
    c.addEventListener("pointermove", (e) => {
      const [x, y] = pos(e);
      const p = this.pointers.get(e.pointerId);
      if (!p) {
        this.hover = this.nearest(x, y);
        this.showTooltip(this.hover, x);
        this.draw();
        return;
      }
      p.x = x; p.y = y;
      if (this.pinch && this.pointers.size === 2) {
        const [a, b] = [...this.pointers.values()];
        const f = this.pinch.dist / (Math.abs(a.x - b.x) || 1);
        const [r0, r1] = this.pinch.range, cc = this.pinch.centre;
        this.setRange(cc - (cc - r0) * f, cc + (r1 - cc) * f);
        this.drag.moved = true;
        return;
      }
      const dx = x - p.x0;
      if (Math.abs(dx) > 4) this.drag.moved = true;
      if (this.drag.moved) {
        const L = this.L, span = this.drag.range[1] - this.drag.range[0];
        const shift = -dx / (L.x1 - L.x0) * span;
        this.tooltip.hidden = true;
        this.setRange(this.drag.range[0] + shift, this.drag.range[1] + shift);
      }
    });
    const up = (e) => {
      const p = this.pointers.get(e.pointerId);
      this.pointers.delete(e.pointerId);
      if (this.pointers.size < 2) this.pinch = null;
      if (p && this.drag && !this.drag.moved && e.type === "pointerup") {
        const hit = this.nearest(p.x, p.y);
        if (hit && !hit.lowres) { this.selected = hit.item; this.onSelect(hit.item); this.draw(); }
      }
    };
    c.addEventListener("pointerup", up);
    c.addEventListener("pointercancel", up);
    c.addEventListener("pointerleave", () => { if (!this.pointers.size) { this.hover = null; this.tooltip.hidden = true; this.draw(); } });
    c.addEventListener("wheel", (e) => {
      if (!e.ctrlKey && !e.metaKey && Math.abs(e.deltaX) < Math.abs(e.deltaY)) return;   // plain scrolling stays with the page
      e.preventDefault();
      const [x] = pos(e);
      if (e.ctrlKey || e.metaKey) this.zoom(e.deltaY > 0 ? 1.25 : 0.8, this.time(x, this.L));
      else { const span = this.range[1] - this.range[0]; this.setRange(this.range[0] + e.deltaX / 600 * span, this.range[1] + e.deltaX / 600 * span); }
    }, { passive: false });
    c.addEventListener("dblclick", (e) => { const [x] = pos(e); this.zoom(0.5, this.time(x, this.L)); });
  }
}

export { ms, DAY };
