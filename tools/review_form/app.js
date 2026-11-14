// Local review form. Data comes from data.js (window.REVIEW_DATA), written by tools/build_review.py.
// Verdicts are kept in the browser's storage as they are entered and written to a CSV file:
// curation/human_review.csv of the repository, which tools/build_db.py reads.

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
const JCG = { anomaly: "異常あり", none: "特異事象なし", not_visible: "視認できず", other: "その他" };

const S = {
  status: "pending", sort: "imp", q: "", high: true, low: true, jcg: false, classes: new Set(Object.keys(LABEL)),
  shown: 200, current: null, pass: 0, list: [], fileHandle: null, dirty: false,
};
let reviews = {};
let embedded = "";     // the reviews as the CSV file had them when the form was built

// Done: reviewed in this form, or judged by the author before the form existed (status in the tables).
const isDone = (e) => e.id in reviews || e.status === "human-reviewed";

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
const today = () => new Date().toISOString().slice(0, 10);
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

// ---------------------------------------------------------------- storage and CSV

function csvText() {
  const q = (v) => { const s = v === null || v === undefined ? "" : String(v); return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s; };
  const ids = Object.keys(reviews).sort();
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

function mergeRows(rows) {
  let n = 0;
  for (const r of rows) {
    if (!r.episode_id || !(r.verdict in LABEL) || r.verdict === "unreviewed") continue;
    const old = reviews[r.episode_id];
    // The later review wins; a row of the same day replaces what the browser holds.
    if (!old || (r.reviewed_at || "") >= (old.reviewed_at || "")) {
      reviews[r.episode_id] = { verdict: r.verdict, cause: r.cause || "", comment: r.comment || "", reviewed_at: r.reviewed_at || today() };
      n++;
    }
  }
  return n;
}

function loadStored() {
  reviews = {};
  mergeRows(Object.entries(D.reviews || {}).map(([episode_id, r]) => ({ episode_id, ...r })));
  embedded = csvText();
  try {
    const kept = JSON.parse(localStorage.getItem(STORE) || "{}");
    mergeRows(Object.entries(kept).map(([episode_id, r]) => ({ episode_id, ...r })));
  } catch { /* storage unavailable or damaged: the embedded reviews stand */ }
  S.dirty = csvText() !== embedded;
}

async function persist() {
  try { localStorage.setItem(STORE, JSON.stringify(reviews)); } catch { /* the file is the record */ }
  if (S.fileHandle) {
    try {
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
  const n = Object.keys(reviews).length;
  const node = $("save-state");
  if (S.fileHandle && !S.dirty) { node.className = "state"; node.textContent = `${S.fileHandle.name} に保存済み (${n} 件)`; }
  else if (S.fileHandle) { node.className = "state warn"; node.textContent = `${S.fileHandle.name} への書き込みに失敗しました。ダウンロードで保存してください`; }
  else if (S.dirty) { node.className = "state warn"; node.textContent = "まだファイルに保存していない確認があります。保存先を選ぶか、ダウンロードしてください"; }
  else { node.className = "state"; node.textContent = n ? `human_review.csv の ${n} 件を読み込み済み` : "保存先は未設定です"; }
}

async function pickFile() {
  if (!window.showSaveFilePicker) { alert("このブラウザはファイルへの直接保存に対応していません。「CSV をダウンロード」を使ってください。"); return; }
  try {
    S.fileHandle = await window.showSaveFilePicker({
      suggestedName: "human_review.csv", types: [{ description: "CSV", accept: { "text/csv": [".csv"] } }],
    });
    await persist();
  } catch (err) { if (err.name !== "AbortError") console.error(err); }
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
    return true;
  });
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
  $("count").textContent = `この条件で ${S.list.length} 件`;
  const box = clear($("list"));
  for (const e of S.list.slice(0, S.shown)) {
    const r = reviews[e.id];
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
      onclick: () => { S.classes.has(c) ? S.classes.delete(c) : S.classes.add(c); S.shown = 200; drawChips(); drawList(); },
    }, el("i", { class: `dot ${c}` }), LABEL[c]));
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
  if (cur) $("strip").scrollLeft = cur.offsetLeft - $("strip").clientWidth / 2 + 54;
}

function drawDetail() {
  const e = S.current, v = vol(e), r = reviews[e.id];
  const main = clear($("detail"));
  const link = `${D.site}volcano.html?id=${encodeURIComponent(e.v)}&ep=${encodeURIComponent(e.id)}&lang=ja`;
  main.append(
    el("div", { class: "head" },
      el("h2", { text: volName(e) }), v.name_ja ? el("span", { class: "alt", text: v.name }) : null,
      badge(e.cls), isDone(e) ? el("span", { class: "tag human", text: `human-reviewed${r ? " " + r.reviewed_at : ""}` }) : null),
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
      el("figure", {}, el("a", { id: "big-link", target: "_blank", rel: "noopener" }, el("img", { id: "big", class: "big", alt: "" })),
        el("div", { class: "halves" }, el("span", { text: "真色" }), el("span", { text: "短波長赤外の合成" }))),
      el("div", { class: "cap", id: "cap" }),
      el("div", { class: "strip", id: "strip" }, ...e.passes.map((p, i) => el("button", {
        type: "button", class: p[13] === "a" ? "alert" : null, title: `${p[1]} ${p[2]} ${ROLE[p[13]]}`, onclick: () => { S.pass = i; drawPass(); },
      }, el("img", { loading: "lazy", alt: "", src: quicklook(p), width: 104, height: 104 }),
        el("span", { class: "t" }, p[1].slice(0, 10), p[13] === "a" ? el("i", { text: ` ${p[3]}` }) : null)))));
  } else {
    const url = `${D.image_base}/${e.image}`;
    viewer.append(
      el("div", { class: "sheetbox" }, el("a", { href: url, target: "_blank", rel: "noopener" }, el("img", { class: "sheet", alt: "", src: url }))),
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
  if (e.tier === "highres") drawPass();
}

function formFor(e, r) {
  const chosen = r ? r.verdict : "";
  const form = el("form", { class: "form", onsubmit: (ev) => { ev.preventDefault(); save(true); } },
    el("h3", { text: "作者の判定" }),
    el("div", { class: "verdicts" }, ...D.classes.map((c, i) => el("label", { class: c === e.cls ? "current" : null },
      el("kbd", { text: String(i + 1) }), el("i", { class: `dot ${c}` }),
      el("span", { class: "lab" }, el("input", { type: "radio", name: "verdict", value: c, checked: c === chosen, onchange: syncCause }), " ", LABEL[c],
        c === e.cls ? " (いまの区分)" : "")))),
    el("select", { id: "cause", "aria-label": "原因" }, el("option", { value: "", text: "原因 (火山性ではない場合)" }),
      ...D.causes.map((c) => el("option", { value: c, text: CAUSE[c] || c, selected: (r ? r.cause : e.cause) === c }))),
    el("textarea", { id: "comment", placeholder: "コメント (任意。公開の表に作者の判定として載ります)" }),
    el("div", { class: "actions" },
      el("button", { type: "submit", class: "primary", text: "保存して次へ (Enter)" }),
      el("button", { type: "button", text: "いまの区分で確認 (A)", onclick: agree }),
      el("button", { type: "button", text: "飛ばす (J)", onclick: () => step(1) }),
      r ? el("button", { type: "button", text: "確認を取り消す", onclick: undo }) : null),
    r ? el("div", { class: "saved", text: `${r.reviewed_at} に確認済み: ${LABEL[r.verdict]}` }) : null,
    el("div", { class: "small", text: "破線の枠がいまの区分です。確認すると、公開の表でこのエピソードが human-reviewed になります。" }));
  form.querySelector("#comment").value = r ? r.comment : "";
  setTimeout(syncCause, 0);
  return form;
}

function syncCause() {
  const v = document.querySelector('input[name="verdict"]:checked');
  const cause = $("cause");
  if (cause) cause.disabled = !v || v.value !== "nonvolcanic";
}

function setVerdict(c) {
  const input = document.querySelector(`input[name="verdict"][value="${c}"]`);
  if (input) { input.checked = true; syncCause(); }
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
  const cause = v.value === "nonvolcanic" ? ($("cause").value || "other") : "";
  reviews[e.id] = { verdict: v.value, cause, comment: $("comment").value.trim().replace(/\s*\n\s*/g, " "), reviewed_at: today() };
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
  delete reviews[S.current.id];
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
  drawChips();
  drawList();
  showSaveState();
  if (S.list.length) open(S.list[0]);

  $("f-status").addEventListener("change", (e) => { S.status = e.target.value; S.shown = 200; drawList(); });
  $("f-sort").addEventListener("change", (e) => { S.sort = e.target.value; drawList(); });
  $("f-q").addEventListener("input", (e) => { S.q = e.target.value; S.shown = 200; drawList(); });
  $("f-high").addEventListener("change", (e) => { S.high = e.target.checked; drawList(); });
  $("f-low").addEventListener("change", (e) => { S.low = e.target.checked; drawList(); });
  $("f-jcg").addEventListener("change", (e) => { S.jcg = e.target.checked; S.shown = 200; drawList(); });
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
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "textarea" || tag === "select" || (tag === "input" && e.target.type !== "radio")) {
      if (e.key === "Escape") e.target.blur();
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (k >= "1" && k <= String(D.classes.length)) { setVerdict(D.classes[Number(k) - 1]); e.preventDefault(); }
    else if (k === "a") { agree(); e.preventDefault(); }
    else if (k === "enter") { save(true); e.preventDefault(); }
    else if (k === "j" || k === "arrowdown") { step(1); e.preventDefault(); }
    else if (k === "k" || k === "arrowup") { step(-1); e.preventDefault(); }
    else if (k === "arrowright" && S.current && S.current.passes.length) { S.pass = Math.min(S.pass + 1, S.current.passes.length - 1); drawPass(); e.preventDefault(); }
    else if (k === "arrowleft" && S.current && S.current.passes.length) { S.pass = Math.max(S.pass - 1, 0); drawPass(); e.preventDefault(); }
    else if (k === "c") { const c = $("comment"); if (c) { c.focus(); e.preventDefault(); } }
  });
  window.addEventListener("beforeunload", (e) => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });
}

start();
