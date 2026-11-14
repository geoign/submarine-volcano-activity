// Local review form. Data comes from data.js (window.REVIEW_DATA), written by tools/build_review.py.
// Verdicts are kept in the browser's storage as they are entered and written to a CSV file:
// curation/human_review.csv of the repository, which tools/build_db.py reads.
//
// The file is the record and more than one place can write it (another tab, another browser), so
// nothing is written without reading first: every save merges what the storage and the file hold
// now, and the later entry of an episode wins. A withdrawn review stays in the storage as an
// entry without a verdict, so that an older copy of it cannot come back.

"use strict";

const D = window.REVIEW_DATA;
const $ = (id) => document.getElementById(id);
const STORE = "submvolc-human-review-v1";
const COLUMNS = ["episode_id", "verdict", "cause", "comment", "reviewed_at"];
const LABEL = {
  known: "既知の噴火期間", likely: "火山性の可能性が高い", possible: "火山性の可能性あり", recurrent: "繰り返す変色",
  airborne: "大気中の帯", undetermined: "判断がつかない", nonvolcanic: "火山性ではない", unreviewed: "未判定",
};
const CAUSE = {
  cloud: "雲", cloud_shadow: "雲の影", sun_glint: "サングリント", reef_or_shoal: "礁・浅瀬", land_or_surf: "陸・砕波",
  land_or_ice: "陸・氷", bloom: "ブルーム", sediment_plume: "濁り", ship_wake: "航跡",
  sensor_artifact: "センサーや製品による見かけ", neighbour_eruption: "隣の火山の噴火", persistent: "その場所のいつもの姿", other: "その他",
};
const PH = { dw: "変色水", fl: "浮遊物", nl: "新しい陸", th: "熱異常", sc: "区域の水の色", ap: "大気中の帯" };
const BASIS = {
  catalogue: "噴火期間と日付で照合", ai_review: "AI の判定", ai_review_partial: "AI の判定 (重なる別のエピソードのもの)",
  rule: "規則", lead_review: "報告書の結論", owner: "作者の判定", "": "判定なし",
};
const ROLE = { a: "警戒", q: "期間内", b: "前", c: "後" };
const JCG = { anomaly: "記録あり", none: "特異事象なし", not_visible: "視認できず", other: "その他" };
const BASE = { quiet: "静穏", frequent: "頻繁", persistent: "常時" };
// Keys of the causes of a "nonvolcanic" verdict, in the order of D.causes.
const CAUSE_KEY = {
  cloud: "q", cloud_shadow: "w", sun_glint: "e", reef_or_shoal: "r", land_or_surf: "t", land_or_ice: "y", bloom: "u",
  sediment_plume: "i", ship_wake: "o", sensor_artifact: "p", neighbour_eruption: "z", persistent: "x", other: "v",
};
const KEY_CAUSE = Object.fromEntries(Object.entries(CAUSE_KEY).map(([c, k]) => [k, c]));
const ENH = ["なし", "中", "強"];
// Conveniences of this browser, not records: the author's changes to the set of volcanoes left out
// (volcano id -> 0 or 1, over the default of data.js) and the view settings.
const STEADY = "submvolc-review-steady-v1";
const PREFS = "submvolc-review-prefs-v1";
const IDB = { name: "submvolc-review", store: "handles", key: "csv" };

const S = {
  status: "pending", sort: "imp", q: "", high: true, low: true, jcg: false, classes: new Set(Object.keys(LABEL)),
  shown: 200, current: null, pass: 0, list: [], fileHandle: null, dirty: false,
  hideSteady: false, hidden: { n: 0, v: 0 }, grid: false, enh: 0, preload: [],
};
let steadyOv = {};
let reviews = {};
let embedded = "";     // the reviews as the CSV file had them when the form was built

// The review of an episode, if there is one that has not been withdrawn.
const rev = (id) => (reviews[id] && reviews[id].verdict ? reviews[id] : null);
// Passes were added to the episode after the day it was reviewed.
const grown = (e, r) => e.e > (r.reviewed_at || "").slice(0, 10);
// Done: reviewed in this form and not grown since, or judged by the author before the form existed
// (status in the tables). A withdrawn review is not done, whatever the tables still say.
const isDone = (e) => (e.id in reviews ? Boolean(rev(e.id)) && !grown(e, reviews[e.id]) : e.status === "human-reviewed");

// ---------------------------------------------------------------- small helpers

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return node;
}
const clear = (node) => { while (node.firstChild) node.removeChild(node.firstChild); return node; };
// Local time with its offset: the day of a review is the author's day, and entries sort by it.
function stamp() {
  const d = new Date(), p = (n) => String(n).padStart(2, "0"), off = -d.getTimezoneOffset();
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
    + `${off < 0 ? "-" : "+"}${p(Math.floor(Math.abs(off) / 60))}:${p(Math.abs(off) % 60)}`;
}
const when = (r) => (r.reviewed_at || "").slice(0, 16).replace("T", " ");
const vol = (e) => D.volcanoes[e.v] || { name: e.v, name_ja: "", country: "" };
const volName = (e) => vol(e).name_ja || vol(e).name;
const phenomena = (code) => (code || "").split("+").filter(Boolean).map((p) => PH[p] || p).join("、");
const range = (a, b) => (a === b ? a : `${a} 〜 ${b}`);
const badge = (cls) => el("span", { class: "badge" }, el("i", { class: `dot ${cls}` }), LABEL[cls] || cls);

function quicklook(p) {
  const t = p[1];
  const stamp = t.slice(0, 4) + t.slice(5, 7) + t.slice(8, 10) + "T" + t.slice(11, 13) + t.slice(14, 16);
  return `${D.image_base}/ql/${p[0]}/${p[0]}_${stamp}_${p[2]}.jpg`;
}

// ---------------------------------------------------------------- view settings (browser storage, optional)

function loadJSON(key) {
  try {
    const v = JSON.parse(localStorage.getItem(key) || "{}");
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  } catch { return {}; }
}
function saveJSON(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* the form works without storage */ }
}

function loadPrefs() {
  const p = loadJSON(PREFS);
  const bool = (k) => { if (typeof p[k] === "boolean") S[k] = p[k]; };
  ["high", "low", "jcg", "hideSteady", "grid"].forEach(bool);
  if (["pending", "done", "all"].includes(p.status)) S.status = p.status;
  if (["imp", "new", "old", "volcano"].includes(p.sort)) S.sort = p.sort;
  if ([0, 1, 2].includes(p.enh)) S.enh = p.enh;
  if (Array.isArray(p.classes)) S.classes = new Set(p.classes.filter((c) => c in LABEL));
  steadyOv = loadJSON(STEADY);
}
function savePrefs() {
  saveJSON(PREFS, {
    status: S.status, sort: S.sort, high: S.high, low: S.low, jcg: S.jcg, classes: [...S.classes],
    hideSteady: S.hideSteady, grid: S.grid, enh: S.enh,
  });
}

// In the set of volcanoes left out by the filter: the author's choice, else the default of the build.
const isSteady = (vid) => (vid in steadyOv ? Boolean(steadyOv[vid]) : Boolean((D.volcanoes[vid] || {}).steady));
const leftOut = (vid) => S.hideSteady && isSteady(vid);
function setSteady(vid, on) { steadyOv[vid] = on ? 1 : 0; saveJSON(STEADY, steadyOv); }

// ---------------------------------------------------------------- storage and CSV

function csvText() {
  const q = (v) => { const s = v === null || v === undefined ? "" : String(v); return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s; };
  const ids = Object.keys(reviews).filter(rev).sort();
  return [COLUMNS.join(","), ...ids.map((id) => [id, reviews[id].verdict, reviews[id].cause, reviews[id].comment, reviews[id].reviewed_at].map(q).join(","))].join("\n") + "\n";
}

function parseCSV(text) {
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else quoted = false; }
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { row.push(field); field = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(field); rows.push(row); row = []; field = "";
    } else field += ch;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  const head = rows.shift() || [];
  return rows.filter((r) => r.length > 1 || r[0] !== "").map((r) => Object.fromEntries(head.map((h, k) => [h, r[k] ?? ""])));
}

// Take rows into the reviews held here. The later entry of an episode wins; what is held here stays
// when the two are equally old. Entries without a verdict (withdrawn reviews) come from the storage only.
function mergeRows(rows, withdrawn) {
  let n = 0;
  for (const r of rows) {
    if (!r.episode_id) continue;
    if (r.verdict ? (!(r.verdict in LABEL) || r.verdict === "unreviewed") : !withdrawn) continue;
    const old = reviews[r.episode_id];
    if (!old || (r.reviewed_at || "") > (old.reviewed_at || "")) {
      reviews[r.episode_id] = { verdict: r.verdict || "", cause: r.cause || "", comment: r.comment || "", reviewed_at: r.reviewed_at || stamp() };
      n++;
    }
  }
  return n;
}

function mergeStorage() {
  try {
    const kept = JSON.parse(localStorage.getItem(STORE) || "{}");
    return mergeRows(Object.entries(kept).map(([episode_id, r]) => ({ episode_id, ...r })), true);
  } catch { return 0; /* storage unavailable or damaged */ }
}

// What the chosen file holds now. Returns false when it could not be read (then it is not written).
async function mergeFile() {
  if (!S.fileHandle) return true;
  try {
    mergeRows(parseCSV(await (await S.fileHandle.getFile()).text()));
    return true;
  } catch (err) {
    if (err.name === "NotFoundError") return true;      // a new file
    console.error(err);
    return false;
  }
}

function loadStored() {
  reviews = {};
  mergeRows(Object.entries(D.reviews || {}).map(([episode_id, r]) => ({ episode_id, ...r })));
  embedded = csvText();
  mergeStorage();
  S.dirty = csvText() !== embedded;
}

async function persist() {
  mergeStorage();                                 // another tab may have saved since
  const readable = await mergeFile();             // and the file may hold more than this tab knows
  try { localStorage.setItem(STORE, JSON.stringify(reviews)); } catch { /* the file is the record */ }
  if (S.fileHandle) {
    try {
      if (!readable) throw new Error("the file could not be read, so it is not overwritten");
      const w = await S.fileHandle.createWritable();
      await w.write(csvText());
      await w.close();
      S.dirty = false;
    } catch (err) {
      S.dirty = true;
      console.error(err);
    }
  } else S.dirty = csvText() !== embedded;
  showSaveState();
}

function showSaveState() {
  const n = Object.keys(reviews).filter(rev).length;
  const node = $("save-state");
  if (S.fileHandle && !S.dirty) { node.className = "state"; node.textContent = `${S.fileHandle.name} に保存済み (${n} 件)`; }
  else if (S.fileHandle) { node.className = "state warn"; node.textContent = `${S.fileHandle.name} への書き込みに失敗しました。ダウンロードで保存してください`; }
  else if (S.dirty) { node.className = "state warn"; node.textContent = "まだファイルに保存していない確認があります。保存先を選ぶか、ダウンロードしてください"; }
  else { node.className = "state"; node.textContent = n ? `human_review.csv の ${n} 件を読み込み済み` : "保存先は未設定です"; }
  $("file-hint").hidden = Boolean(S.fileHandle);
}

async function pickFile() {
  if (!window.showSaveFilePicker) { alert("このブラウザはファイルへの直接保存に対応していません。「CSV をダウンロード」を使ってください。"); return; }
  try {
    const handle = await window.showSaveFilePicker({
      id: "submvolc-review",          // the browser opens the dialog in the folder used last time
      suggestedName: "human_review.csv", types: [{ description: "CSV", accept: { "text/csv": [".csv"] } }],
    });
    await useHandle(handle);
    rememberHandle(handle);
  } catch (err) { if (err.name !== "AbortError") console.error(err); }
}

// Write to this file from now on. persist() reads it first: reviews it already holds are kept.
// The open episode is drawn again only when the file brought another review of it: a comment that
// is being typed is not thrown away.
async function useHandle(handle) {
  S.fileHandle = handle;
  $("reuse").hidden = true;
  const held = S.current ? JSON.stringify(reviews[S.current.id] || null) : "";
  await persist();
  drawList();
  if (S.current && JSON.stringify(reviews[S.current.id] || null) !== held) drawDetail();
}

// The chosen file is remembered between sessions in IndexedDB. Every failure leaves the form without it.
function openHandles() {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) { reject(new Error("no IndexedDB")); return; }
    const req = indexedDB.open(IDB.name, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(IDB.store);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function rememberHandle(handle) {
  try {
    const db = await openHandles();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(IDB.store, "readwrite");
      tx.objectStore(IDB.store).put(handle, IDB.key);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
    db.close();
    return true;
  } catch (err) { console.warn(err); return false; }
}

async function storedHandle() {
  try {
    const db = await openHandles();
    const handle = await new Promise((resolve, reject) => {
      const req = db.transaction(IDB.store, "readonly").objectStore(IDB.store).get(IDB.key);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    });
    db.close();
    return handle;
  } catch (err) { console.warn(err); return null; }
}

// At start: take the file of the last session again. Granted: at once; to be asked: a button in the header.
async function reconnect() {
  try {
    const handle = await storedHandle();
    if (!handle || S.fileHandle || typeof handle.queryPermission !== "function") return;
    const state = await handle.queryPermission({ mode: "readwrite" });
    if (state === "granted") {
      await handle.getFile();          // a file that is gone throws here and is not created again
      if (!S.fileHandle) await useHandle(handle);
    } else if (state === "prompt") {
      const button = $("reuse");
      button.textContent = `前回の保存先 (${handle.name}) を使う`;
      button.onclick = async () => {
        try {
          if (await handle.requestPermission({ mode: "readwrite" }) !== "granted") return;
          await handle.getFile();
          if (!S.fileHandle) await useHandle(handle);
          else button.hidden = true;
        } catch (err) { console.warn(err); button.hidden = true; }
      };
      button.hidden = false;
    }
  } catch (err) { console.warn(err); }
}

function download() {
  const url = URL.createObjectURL(new Blob([csvText()], { type: "text/csv;charset=utf-8" }));
  const a = el("a", { href: url, download: "human_review.csv" });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---------------------------------------------------------------- list

function filtered() {
  const q = S.q.trim().toLowerCase();
  // Episodes that match every other condition but belong to a volcano left out: counted, so that a
  // search for such a volcano does not look empty without a reason.
  let hidden = 0;
  const hiddenVolcanoes = new Set();
  const rows = D.episodes.filter((e) => {
    const done = isDone(e);
    if (S.status === "pending" && done) return false;
    if (S.status === "done" && !done) return false;
    if (!S.classes.has(e.cls)) return false;
    if (e.tier === "highres" ? !S.high : !S.low) return false;
    if (S.jcg && !e.jh) return false;
    if (q) {
      const v = vol(e);
      if (![v.name, v.name_ja, v.country, e.id].some((s) => (s || "").toLowerCase().includes(q))) return false;
    }
    if (leftOut(e.v)) { hidden++; hiddenVolcanoes.add(e.v); return false; }
    return true;
  });
  S.hidden = { n: hidden, v: hiddenVolcanoes.size };
  if (S.sort === "new") rows.sort((a, b) => (a.s < b.s ? 1 : -1));
  else if (S.sort === "old") rows.sort((a, b) => (a.s > b.s ? 1 : -1));
  else if (S.sort === "volcano") rows.sort((a, b) => vol(a).name.localeCompare(vol(b).name) || (a.s > b.s ? 1 : -1));
  else rows.sort((a, b) => b.imp - a.imp || (a.s > b.s ? 1 : -1));
  return rows;
}

function drawList() {
  S.list = filtered();
  const done = D.episodes.filter(isDone).length;
  $("progress").textContent = `確認済み ${done} / ${D.episodes.length} 件`;
  $("count").textContent = `この条件で ${S.list.length} 件`
    + (S.hidden.n ? ` · 常時活動の ${S.hidden.v} 火山 (${S.hidden.n} 件) を除外中` : "");
  const box = clear($("list"));
  for (const e of S.list.slice(0, S.shown)) {
    const r = rev(e.id);
    const li = el("li", { "aria-current": String(S.current && S.current.id === e.id), onclick: () => open(e) },
      el("i", { class: `dot ${r ? r.verdict : e.cls}` }),
      el("span", {}, el("span", { class: "name", text: volName(e) }),
        e.jh ? el("span", { class: "jcg", title: "海域火山データベースに、同じ時期のこの区域の異常の記録がある", text: "海保" }) : null,
        el("div", { class: "meta", text: `${range(e.s, e.e)} · ${e.tier === "lowres" ? "低解像度" : `${e.z.split("-").pop()} · ${phenomena(e.ph) || "-"}`}` })),
      isDone(e) ? el("span", { class: "done", text: "済" }) : el("span", { class: "imp", text: e.imp.toFixed(0) }));
    li.dataset.id = e.id;
    box.append(li);
  }
  $("more").hidden = S.list.length <= S.shown;
}

function drawChips() {
  const box = clear($("f-classes"));
  for (const c of Object.keys(LABEL)) {
    box.append(el("button", {
      type: "button", class: "chip", "aria-pressed": String(S.classes.has(c)),
      onclick: () => { S.classes.has(c) ? S.classes.delete(c) : S.classes.add(c); S.shown = 200; savePrefs(); drawChips(); drawList(); },
    }, el("i", { class: `dot ${c}` }), LABEL[c]));
  }
}

// ---------------------------------------------------------------- volcanoes left out

function drawSteadyButton() {
  const b = $("steady-btn");
  if (b && S.current) b.textContent = leftOut(S.current.v) ? "この火山を一覧に戻す" : "この火山を一覧から除く";
}

// After the set of volcanoes left out changed. The open episode stays open while it is in the list;
// if it left the list and openNext is true, the next one is opened.
function afterSteadyChange(openNext) {
  const cur = S.current;
  const index = cur ? S.list.findIndex((x) => x.id === cur.id) : -1;
  S.shown = 200;
  drawList();
  drawSteadyButton();
  if (openNext && cur && !S.list.some((x) => x.id === cur.id)) {
    const target = S.list[Math.min(Math.max(index, 0), S.list.length - 1)];
    if (target) open(target);
  }
  if ($("steady-dlg").open) drawSteadyDialog();
}

// The button in the head of the open episode.
function toggleCurrentVolcano() {
  if (!S.current) return;
  const vid = S.current.v;
  if (leftOut(vid)) setSteady(vid, false);
  else {
    setSteady(vid, true);
    if (!S.hideSteady) { S.hideSteady = true; $("f-steady").checked = true; savePrefs(); }
  }
  afterSteadyChange(true);
}

function drawSteadyDialog() {
  const pending = {};
  for (const e of D.episodes) if (!isDone(e)) pending[e.v] = (pending[e.v] || 0) + 1;
  const rows = Object.entries(D.volcanoes).filter(([, v]) => v.n > 0)
    .sort(([, a], [, b]) => b.act - a.act || b.n - a.n || a.name.localeCompare(b.name));
  const box = clear($("steady-list"));
  for (const [vid, v] of rows) {
    box.append(el("li", {}, el("label", {},
      el("input", { type: "checkbox", checked: isSteady(vid), onchange: (ev) => { setSteady(vid, ev.target.checked); afterSteadyChange(false); } }),
      el("span", { class: "name" }, v.name_ja ? `${v.name_ja} (${v.name})` : v.name,
        (D.volcanoes[vid].steady ? el("span", { class: "def", title: "既定で除く火山", text: "既定" }) : null)),
      el("span", { class: "base", text: BASE[v.base] || v.base || "-" }),
      el("span", { class: "nums", text: `活動の区分 ${v.act} 件 / 全 ${v.n} 件 · 未確認 ${pending[vid] || 0} 件` }))));
  }
}

// ---------------------------------------------------------------- detail

function open(e) {
  S.current = e;
  const firstAlert = e.passes.findIndex((p) => p[13] === "a");
  const peak = e.passes.findIndex((p) => `${p[0]}_${p[1].replaceAll("-", "").replace(":", "")}_${p[2]}` === e.peak);
  S.pass = peak >= 0 ? peak : Math.max(firstAlert, 0);
  drawDetail();
  for (const li of $("list").children) li.setAttribute("aria-current", String(li.dataset.id === e.id));
  const cur = [...$("list").children].find((li) => li.dataset.id === e.id);
  if (cur) cur.scrollIntoView({ block: "nearest" });
}

function drawPass() {
  const e = S.current, p = e.passes[S.pass];
  if (!p) return;
  const url = quicklook(p);
  $("big").src = url;
  $("big-link").href = url;
  const num = (v, unit) => (Number(v) > 0 ? `${v} ${unit}` : "");
  const parts = [
    `${p[1].replace("T", " ")} UTC`, p[2], p[0], `${ROLE[p[13]]}の通過`, p[3] + (p[4] ? ` (${phenomena(p[4])})` : ""),
    Number(p[5]) > 0 ? `変色水 ${p[5]} km²${p[6] && p[6] !== "none" ? ` ${p[6]}` : ""}` : "",
    Number(p[5]) > 0 && p[7] !== "" ? `中心から ${p[7]} km・方位 ${p[8]}°` : "",
    num(p[9], "km² 浮遊物"), num(p[10], "km² 新しい陸"), num(p[11], "高温画素"), num(p[12], "km² 大気中の帯"),
  ].filter(Boolean);
  clear($("cap")).append(el("b", { text: `${S.pass + 1} / ${e.passes.length}` }), " · ", parts.join(" · "));
  [...$("strip").children].forEach((b, i) => b.setAttribute("aria-current", String(i === S.pass)));
  const cur = $("strip").children[S.pass];
  if (cur && !S.grid) $("strip").scrollLeft = cur.offsetLeft - $("strip").clientWidth / 2 + 54;
  const grid = $("grid");
  if (grid) {
    [...grid.children].forEach((b, i) => b.setAttribute("aria-current", String(i === S.pass)));
    const tile = grid.children[S.pass];
    if (tile && S.grid) tile.scrollIntoView({ block: "nearest" });
  }
  // The neighbours are fetched while this one is looked at (kept referenced until the next pass).
  S.preload = [S.pass + 1, S.pass - 1].filter((i) => e.passes[i]).map((i) => {
    const img = new Image();
    img.src = quicklook(e.passes[i]);
    return img;
  });
}

// All passes of the episode as tiles (the true-colour half of each quicklook), or the single view.
function fillGrid() {
  const e = S.current, grid = $("grid");
  if (!grid || grid.childElementCount) return;
  grid.append(...e.passes.map((p, i) => el("button", {
    type: "button", class: p[13] === "a" ? "alert" : null, title: `${p[1]} ${p[2]} ${ROLE[p[13]]}`,
    onclick: () => { S.pass = i; setGrid(false); },
  }, el("img", { loading: "lazy", alt: "", src: quicklook(p), width: 240, height: 240, onerror: (ev) => ev.target.closest("button").classList.add("broken") }),
    el("span", { class: "t" }, `${p[1].slice(0, 16).replace("T", " ")}`, el("br"),
      `${p[2]} · ${ROLE[p[13]]}`, p[3] ? el("i", { text: ` ${p[3]}` }) : null))));
}

function applyGrid() {
  const fig = $("big-fig");
  if (!fig) return;
  if (S.grid) fillGrid();
  fig.hidden = S.grid;
  $("strip").hidden = S.grid;
  $("grid").hidden = !S.grid;
  const b = $("grid-btn");
  b.textContent = S.grid ? "1 枚表示に戻す (G)" : "全通過を並べる (G)";
  b.setAttribute("aria-pressed", String(S.grid));
  drawPass();
}

function setGrid(on) {
  S.grid = on;
  savePrefs();
  applyGrid();
}

// Enhancement of the images: off, medium, strong (a CSS filter, see style.css).
function applyEnh() {
  document.body.dataset.enh = String(S.enh);
  const b = $("enh-btn");
  if (b) { b.textContent = `強調: ${ENH[S.enh]} (H)`; b.setAttribute("aria-pressed", String(S.enh > 0)); }
}

function cycleEnh() {
  S.enh = (S.enh + 1) % ENH.length;
  savePrefs();
  applyEnh();
}

function movePass(dir) {
  const e = S.current;
  if (!e || !e.passes.length) return;
  S.pass = Math.min(Math.max(S.pass + dir, 0), e.passes.length - 1);
  drawPass();
}

function drawDetail() {
  const e = S.current, v = vol(e), r = rev(e.id);
  const main = clear($("detail"));
  const link = `${D.site}volcano.html?id=${encodeURIComponent(e.v)}&ep=${encodeURIComponent(e.id)}&lang=ja`;
  main.append(
    el("div", { class: "head" },
      el("h2", { text: volName(e) }), v.name_ja ? el("span", { class: "alt", text: v.name }) : null,
      badge(e.cls), isDone(e) ? el("span", { class: "tag human", text: `human-reviewed${r ? " " + when(r) : ""}` }) : null,
      el("button", { type: "button", id: "steady-btn", class: "mini", onclick: toggleCurrentVolcano })),
    el("div", { class: "facts" },
      el("span", {}, el("b", { text: range(e.s, e.e) })), el("span", { text: v.country }),
      el("span", { text: e.tier === "lowres" ? "低解像度" : `高解像度 · ${e.z} · ${e.sens}` }),
      el("span", { text: phenomena(e.ph) }), Number(e.dw) > 0 ? el("span", { text: `最大 ${e.dw} km²` }) : null,
      el("span", { text: e.tier === "lowres" ? `火口付近 ${e.nd} 日 / 見えた ${e.ns} 日` : `警戒 ${e.nd} / 使える通過 ${e.ns}` }),
      el("span", { text: `根拠: ${BASIS[e.basis] ?? e.basis}` }), e.interest !== "" ? el("span", { text: `関心度 ${e.interest}` }) : null,
      el("span", { text: `重要度 ${e.imp}` }), el("span", { text: e.id }),
      el("a", { href: link, target: "_blank", rel: "noopener", text: "公開ページ" }),
      v.gvp ? el("a", { href: `https://volcano.si.edu/volcano.cfm?vn=${v.gvp}`, target: "_blank", rel: "noopener", text: "GVP" }) : null));

  const viewer = el("div", { class: "viewer" });
  if (e.tier === "highres") {
    viewer.append(
      el("div", { class: "tools" },
        el("button", { type: "button", id: "grid-btn", class: "mini", onclick: () => setGrid(!S.grid) }),
        el("button", { type: "button", id: "enh-btn", class: "mini", onclick: cycleEnh })),
      el("figure", { id: "big-fig" }, el("a", { id: "big-link", target: "_blank", rel: "noopener" }, el("img", {
        id: "big", class: "big", alt: "",
        onload: (ev) => { ev.target.classList.remove("broken"); ev.target.alt = ""; },
        onerror: (ev) => { ev.target.classList.add("broken"); ev.target.alt = "画像を読み込めませんでした (ネットワークか画像の保管先を確かめてください)"; },
      })),
        el("div", { class: "halves" }, el("span", { text: "真色" }), el("span", { text: "短波長赤外の合成" }))),
      el("div", { class: "cap", id: "cap" }),
      el("div", { class: "strip", id: "strip" }, ...e.passes.map((p, i) => el("button", {
        type: "button", class: p[13] === "a" ? "alert" : null, title: `${p[1]} ${p[2]} ${ROLE[p[13]]}`, onclick: () => { S.pass = i; drawPass(); },
      }, el("img", { loading: "lazy", alt: "", src: quicklook(p), width: 104, height: 104, onerror: (ev) => ev.target.closest("button").classList.add("broken") }),
        el("span", { class: "t" }, p[1].slice(0, 10), p[13] === "a" ? el("i", { text: ` ${p[3]}` }) : null)))),
      el("div", { class: "grid", id: "grid", hidden: true }));
  } else {
    const url = `${D.image_base}/${e.image}`;
    viewer.append(
      el("div", { class: "sheetbox" }, el("a", { href: url, target: "_blank", rel: "noopener" }, el("img", {
        class: "sheet", alt: "", src: url,
        onerror: (ev) => { ev.target.classList.add("broken"); ev.target.alt = "画像を読み込めませんでした (ネットワークか画像の保管先を確かめてください)"; },
      }))),
      el("div", { class: "cap" }, "低解像度の判定用のシート (前後 5 日の VIIRS・MODIS・OLCI の全通過)。",
        el("a", { href: `${D.image_base}/wide/digest/${e.z}.jpg`, target: "_blank", rel: "noopener", text: "火口付近の要約図" })));
  }
  const notes = el("div", {});
  const block = (title, ...body) => { if (body.some(Boolean)) notes.append(el("div", { class: "note" }, el("h3", { text: title }), ...body)); };
  block("AI の所見", e.note_ja ? el("p", { text: e.note_ja }) : null, e.note_en && !e.note_ja ? el("p", { class: "en", text: e.note_en }) : null,
    e.cause ? el("p", { text: `原因の区分: ${CAUSE[e.cause] || e.cause}` }) : null);
  block("これまでの作者の判定", e.owner_ja ? el("p", { text: e.owner_ja }) : null);
  block("区分を個別に直した理由", e.cur_ja ? el("p", { text: e.cur_ja }) : null);
  block("照合した噴火期間・既報の確認", e.known ? el("p", { text: e.known }) : null, e.prior ? el("p", { text: e.prior }) : null,
    e.periods.length ? el("p", { class: "en", text: "この火山の噴火期間: " + e.periods.join(" / ") }) : null);
  if (e.jcg.length) {
    block("海上保安庁の海域火山データベースの観測 (エピソードの前後 30 日)", el("table", {}, ...e.jcg.map((j) => el("tr", { class: j[4] ? null : "away" },
      el("td", { class: "d", text: j[0] }), el("td", { class: j[1] === "anomaly" ? "anomaly" : null, text: JCG[j[1]] || j[1] }),
      el("td", { text: `[${j[2]}${j[4] ? "" : "・この区域の外"}] ${j[3]}` })))));
  }
  viewer.append(notes);
  main.append(el("div", { class: "work" }, viewer, formFor(e, r)));
  drawSteadyButton();
  applyEnh();
  if (e.tier === "highres") applyGrid();      // draws the pass
}

function formFor(e, r) {
  const chosen = r ? r.verdict : "";
  const form = el("form", { class: "form", onsubmit: (ev) => { ev.preventDefault(); save(true); } },
    el("h3", { text: "作者の判定" }),
    // "known" is a match by date with a documented eruption period: it is offered where there is one.
    el("div", { class: "verdicts" }, ...D.classes.map((c, i) => el("label", { class: [c === e.cls ? "current" : "", c === "known" && !e.known ? "off" : ""].join(" ").trim() || null },
      el("kbd", { text: String(i + 1) }), el("i", { class: `dot ${c}` }),
      el("span", { class: "lab" }, el("input", { type: "radio", name: "verdict", value: c, checked: c === chosen, disabled: c === "known" && !e.known, onchange: syncCause }), " ", LABEL[c],
        c === e.cls ? " (いまの区分)" : "", c === "known" && !e.known ? " (照合した噴火期間が無い)" : "")))),
    // A cause key selects "nonvolcanic" and that cause; the group is disabled for any other verdict.
    el("fieldset", { id: "causes", class: "causes" }, el("legend", { text: "原因 (火山性ではない場合)" }),
      ...D.causes.map((c) => el("label", { title: CAUSE[c] || c },
        el("input", { type: "radio", name: "cause", value: c, checked: (r ? r.cause : e.cause) === c }),
        CAUSE_KEY[c] ? el("kbd", { text: CAUSE_KEY[c].toUpperCase() }) : null, el("span", { text: CAUSE[c] || c })))),
    el("div", { class: "comment-tools" },
      el("label", { for: "comment", text: "コメント" }),
      e.tier === "highres" ? el("button", { type: "button", class: "mini", onclick: insertDate, text: "この通過の日付を入れる (D)" }) : null),
    el("textarea", { id: "comment", placeholder: "コメント (任意。公開の表に作者の判定として載ります)" }),
    commonComments(),
    el("div", { class: "actions" },
      el("button", { type: "submit", class: "primary", text: "保存して次へ (Enter)" }),
      el("button", { type: "button", text: "いまの区分で確認 (A)", onclick: agree }),
      el("button", { type: "button", text: "飛ばす (J)", onclick: () => step(1) }),
      r ? el("button", { type: "button", text: "確認を取り消す", onclick: undo }) : null),
    r ? el("div", { class: "saved", text: `${when(r)} に確認済み: ${LABEL[r.verdict]}` }) : null,
    r && grown(e, r) ? el("div", { class: "saved warn", text: `確認のあとに通過が増えています (エピソードの終わりは ${e.e})。もう一度確認してください。` }) : null,
    el("div", { class: "small", text: "破線の枠がいまの区分です。確認すると、公開の表でこのエピソードが human-reviewed になります。" }));
  form.querySelector("#comment").value = r ? r.comment : "";
  setTimeout(syncCause, 0);
  return form;
}

// The comments the author used more than once (reviews held here, by count, then by the latest use),
// as chips. A comment used once is a note on one episode and would only fill the form.
function commonComments() {
  const used = new Map();
  for (const r of Object.values(reviews)) {
    const text = r.verdict ? (r.comment || "").trim() : "";
    if (!text) continue;
    const u = used.get(text) || { n: 0, last: "" };
    u.n++;
    if ((r.reviewed_at || "") > u.last) u.last = r.reviewed_at || "";
    used.set(text, u);
  }
  const top = [...used].filter(([, u]) => u.n > 1)
    .sort(([, a], [, b]) => b.n - a.n || (a.last < b.last ? 1 : a.last > b.last ? -1 : 0)).slice(0, 6);
  if (!top.length) return null;
  return el("div", { class: "cchips" }, ...top.map(([text, u]) => el("button", {
    type: "button", class: "chip", title: `${text} (${u.n} 回)`,
    text: text.length > 28 ? text.slice(0, 27) + "…" : text,
    onclick: () => {
      const box = $("comment");
      box.value = box.value.trim() === "" ? text : box.value.replace(/\s*$/, " ") + text;
      box.focus();
      box.setSelectionRange(box.value.length, box.value.length);
    },
  })));
}

// "MM-DD: " of the pass shown, at the cursor of the comment box.
function insertDate() {
  const e = S.current, box = $("comment");
  if (!e || e.tier !== "highres" || !box) return;
  const p = e.passes[S.pass];
  if (!p) return;
  const start = box.selectionStart ?? box.value.length, end = box.selectionEnd ?? start;
  const before = box.value.slice(0, start);
  const text = (before !== "" && !/\s$/.test(before) ? " " : "") + `${p[1].slice(5, 10)}: `;
  box.focus();
  box.setRangeText(text, start, end, "end");
}

function syncCause() {
  const v = document.querySelector('input[name="verdict"]:checked');
  const causes = $("causes");
  if (causes) causes.disabled = !v || v.value !== "nonvolcanic";
}

function setVerdict(c) {
  const input = document.querySelector(`input[name="verdict"][value="${c}"]`);
  if (input && !input.disabled) { input.checked = true; syncCause(); }
}

function setCause(c) {
  if (!S.current) return;
  setVerdict("nonvolcanic");
  const input = document.querySelector(`input[name="cause"][value="${c}"]`);
  if (input) input.checked = true;
}

function agree() {
  if (!S.current) return;
  if (S.current.cls === "unreviewed") { alert("未判定のエピソードです。区分を選んでください。"); return; }
  setVerdict(S.current.cls);
  save(true);
}

async function save(next) {
  const e = S.current;
  if (!e) return;
  const v = document.querySelector('input[name="verdict"]:checked');
  if (!v) { alert("区分を選んでください。"); return; }
  const c = document.querySelector('input[name="cause"]:checked');
  const cause = v.value === "nonvolcanic" ? (c ? c.value : "other") : "";
  reviews[e.id] = { verdict: v.value, cause, comment: $("comment").value.trim().replace(/\s*\n\s*/g, " "), reviewed_at: stamp() };
  await persist();
  const index = S.list.findIndex((x) => x.id === e.id);
  drawList();
  if (next) {
    // In the list of pending episodes the saved one has gone, so the same index is the next one.
    const target = S.status === "pending" ? S.list[Math.min(index, S.list.length - 1)] : S.list[S.list.findIndex((x) => x.id === e.id) + 1];
    if (target) open(target); else drawDetail();
  } else drawDetail();
}

async function undo() {
  if (!S.current || !confirm("このエピソードの確認を取り消しますか?")) return;
  // An entry without a verdict, newer than the review: older copies in the storage or the file stay out.
  reviews[S.current.id] = { verdict: "", cause: "", comment: "", reviewed_at: stamp() };
  await persist();
  drawList();
  drawDetail();
}

function step(dir) {
  if (!S.list.length) return;
  const i = S.current ? S.list.findIndex((x) => x.id === S.current.id) : -1;
  const target = S.list[Math.min(Math.max(i + dir, 0), S.list.length - 1)];
  if (target) open(target);
}

// ---------------------------------------------------------------- start

function start() {
  if (!D) { $("detail").textContent = "data.js がありません。python tools/build_review.py を実行してください。"; return; }
  loadStored();
  loadPrefs();
  $("f-status").value = S.status;
  $("f-sort").value = S.sort;
  $("f-high").checked = S.high;
  $("f-low").checked = S.low;
  $("f-jcg").checked = S.jcg;
  $("f-steady").checked = S.hideSteady;
  applyEnh();
  drawChips();
  drawList();
  showSaveState();
  if (S.list.length) open(S.list[0]);
  reconnect();

  const filter = (apply) => (e) => { apply(e.target); S.shown = 200; savePrefs(); drawList(); };
  $("f-status").addEventListener("change", filter((t) => { S.status = t.value; }));
  $("f-sort").addEventListener("change", filter((t) => { S.sort = t.value; }));
  $("f-q").addEventListener("input", (e) => { S.q = e.target.value; S.shown = 200; drawList(); });
  $("f-high").addEventListener("change", filter((t) => { S.high = t.checked; }));
  $("f-low").addEventListener("change", filter((t) => { S.low = t.checked; }));
  $("f-jcg").addEventListener("change", filter((t) => { S.jcg = t.checked; }));
  // With the filter switched on, an open episode of a volcano that is now left out gives way to the next one.
  $("f-steady").addEventListener("change", (e) => { S.hideSteady = e.target.checked; savePrefs(); afterSteadyChange(true); });
  $("steady-open").addEventListener("click", () => { drawSteadyDialog(); $("steady-dlg").showModal(); });
  $("steady-close").addEventListener("click", () => $("steady-dlg").close());
  $("steady-reset").addEventListener("click", () => { steadyOv = {}; saveJSON(STEADY, steadyOv); afterSteadyChange(false); });
  $("more").addEventListener("click", () => { S.shown += 300; drawList(); });
  $("pick").addEventListener("click", pickFile);
  $("download").addEventListener("click", download);
  $("import").addEventListener("click", () => $("file").click());
  $("file").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const n = mergeRows(parseCSV(await file.text()));
    e.target.value = "";
    await persist();
    drawList();
    if (S.current) drawDetail();
    alert(`${n} 件を読み込みました。`);
  });
  document.addEventListener("keydown", (e) => {
    // Typing with an input method, and the dialog of volcanoes, keep their keys.
    if (e.isComposing || e.keyCode === 229 || $("steady-dlg").open) return;
    const t = e.target, tag = (t.tagName || "").toLowerCase();
    if (tag === "textarea" || tag === "select" || (tag === "input" && !["radio", "checkbox", "button"].includes(t.type))) {
      if (t.id === "comment" && e.altKey && !e.ctrlKey && !e.metaKey && e.code === "KeyD") { insertDate(); e.preventDefault(); }
      else if (e.key === "Escape") t.blur();
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    // Enter and Space on a button, a link or a checkbox do what that control does, not "save and next".
    if ((tag === "button" || tag === "a" || (tag === "input" && t.type !== "radio")) && (e.key === "Enter" || e.key === " ")) return;
    const k = e.key.toLowerCase();
    if (k >= "1" && k <= String(D.classes.length)) { setVerdict(D.classes[Number(k) - 1]); e.preventDefault(); }
    else if (k === "a") { agree(); e.preventDefault(); }
    else if (k === "enter") { save(true); e.preventDefault(); }
    else if (k === "j" || k === "arrowdown") { step(1); e.preventDefault(); }
    else if (k === "k" || k === "arrowup") { step(-1); e.preventDefault(); }
    else if (k === "arrowright" && S.current && S.current.passes.length) { movePass(1); e.preventDefault(); }
    else if (k === "arrowleft" && S.current && S.current.passes.length) { movePass(-1); e.preventDefault(); }
    else if (k === "c") { const c = $("comment"); if (c) { c.focus(); e.preventDefault(); } }
    else if (k === "d") { if (S.current && S.current.tier === "highres") { insertDate(); e.preventDefault(); } }
    else if (k === "g") { if ($("big-fig")) { setGrid(!S.grid); e.preventDefault(); } }
    else if (k === "h") { cycleEnh(); e.preventDefault(); }
    else if (k.length === 1 && KEY_CAUSE[k] && D.causes.includes(KEY_CAUSE[k])) { setCause(KEY_CAUSE[k]); e.preventDefault(); }
  });
  window.addEventListener("beforeunload", (e) => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });
  // Another tab of the form saved: take its reviews (the open episode is left as it is being edited).
  // A tab that has the file writes it again, so the file follows whichever tab saved.
  window.addEventListener("storage", async (e) => {
    if (e.key !== STORE || !mergeStorage()) return;
    if (S.fileHandle) await persist();
    else { S.dirty = csvText() !== embedded; showSaveState(); }
    drawList();
  });
}

start();
