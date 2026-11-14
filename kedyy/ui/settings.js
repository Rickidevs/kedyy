"use strict";
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let state = null;

/* Replace the native number arrows with − / + buttons (hold to repeat). */
function makeStepper(input) {
  const wrap = document.createElement("span");
  wrap.className = "stepper";
  input.replaceWith(wrap);
  const minus = Object.assign(document.createElement("button"), { type: "button", textContent: "−" });
  const plus = Object.assign(document.createElement("button"), { type: "button", textContent: "+" });
  wrap.append(minus, input, plus);
  const lim = () => [input.min === "" ? -Infinity : +input.min, input.max === "" ? Infinity : +input.max];
  const sync = () => { const [lo, hi] = lim(), v = +input.value; minus.disabled = v <= lo; plus.disabled = v >= hi; };
  const step = (d) => {
    const [lo, hi] = lim();
    const v = Math.max(lo, Math.min(hi, (parseInt(input.value, 10) || 0) + d));
    if (String(v) !== input.value) { input.value = v; input.dispatchEvent(new Event("input")); }
    sync();
  };
  [[minus, -1], [plus, 1]].forEach(([b, d]) => {
    let t1, t2;
    const stop = () => { clearTimeout(t1); clearInterval(t2); if (b._moved) input.dispatchEvent(new Event("change")); b._moved = false; };
    b.addEventListener("mousedown", (e) => {
      e.preventDefault(); b._moved = true; step(d);
      t1 = setTimeout(() => (t2 = setInterval(() => step(d), 70)), 380);
    });
    ["mouseup", "mouseleave"].forEach((ev) => b.addEventListener(ev, stop));
  });
  input.addEventListener("input", sync);
  input._sync = sync;
}
document.querySelectorAll('input[type="number"]').forEach(makeStepper);

function post(msg) {
  try { window.webkit.messageHandlers.settings.postMessage(JSON.stringify(msg)); }
  catch (e) { console.log("post", msg); }
}

function toast(text, err = false) {
  const el = $("#toast");
  el.textContent = text;
  el.className = "show" + (err ? " err" : "");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.className = err ? "err" : ""), err ? 5000 : 2200);
}

function confirmBox(text) {
  return new Promise((res) => {
    $("#modal-text").textContent = text;
    $("#modal").hidden = false;
    const done = (v) => { $("#modal").hidden = true; res(v); };
    $("#modal-yes").onclick = () => done(true);
    $("#modal-no").onclick = () => done(false);
  });
}

/* ---------- from Python ---------- */
window.setState = function (st) {
  state = st;
  const s = st.settings;

  const sel = $("#language");
  sel.innerHTML = `<option value="auto">${esc(t("lang_auto"))}</option>` +
    Object.entries(st.languages).map(([code, name]) => `<option value="${esc(code)}">${esc(name)}</option>`).join("");

  $$("[data-k]").forEach((el) => {
    const k = el.dataset.k;
    if (el.classList.contains("seg")) {
      el.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === s[k]));
    } else if (el.type === "checkbox") {
      el.checked = !!s[k];
    } else if (document.activeElement !== el) {
      el.value = s[k];
      if (el._sync) el._sync();
    }
  });
  $("#retire-row").classList.toggle("off", !s.retire);

  $("#st-correct").textContent = st.stats.correct;
  $("#st-wrong").textContent = st.stats.wrong;
  $("#st-learned").textContent = st.stats.learned;
  $("#st-total").textContent = st.stats.total;
  $("#fmt").textContent = t("formats_files", { list: st.formats.join(", ") });

  if (!s.enabled) $("#next").textContent = t("paused");
  else if (st.next_at) {
    const time = new Date(st.next_at * 1000).toLocaleTimeString(window.I18N._code || undefined, { hour: "2-digit", minute: "2-digit" });
    $("#next").textContent = t("next_at", { time });
  } else $("#next").textContent = t("on_screen");

  const off = new Set(s.disabled_decks);
  $("#decks").innerHTML = st.decks.length ? st.decks.map((d) => `
    <li class="${off.has(d.file) ? "off" : ""}">
      <input type="checkbox" class="switch" data-g="${esc(d.file)}" ${off.has(d.file) ? "" : "checked"}>
      <span class="name">${esc(d.name)}${d.front && d.back ? `<small>${esc(d.front)} → ${esc(d.back)}</small>` : `<small>${esc(d.file)}</small>`}</span>
      <span class="count">${esc(t("cards_count", { n: d.count }))}</span>
      <button class="del" data-del="${esc(d.file)}" title="${esc(t("delete"))}">🗑</button>
    </li>`).join("") : `<li class="empty">${esc(t("no_decks"))}</li>`;

  if (st.toast) toast(st.toast);
  if (st.error) toast(st.error, true);
};

/* ---------- save changes ---------- */
function collect() {
  const out = {};
  $$("[data-k]").forEach((el) => {
    const k = el.dataset.k;
    if (el.classList.contains("seg")) out[k] = el.querySelector("button.on")?.dataset.v;
    else if (el.type === "checkbox") out[k] = el.checked;
    else if (el.tagName === "SELECT") out[k] = el.value;
    else out[k] = parseInt(el.value, 10) || 0;
  });
  return out;
}
let saveT = null;
function save(delay = 0) {
  clearTimeout(saveT);
  saveT = setTimeout(() => post({ type: "save", settings: collect() }), delay);
}

$$("input[data-k]").forEach((el) => {
  if (el.type === "checkbox") el.addEventListener("change", () => save());
  else {
    el.addEventListener("input", () => save(900));
    el.addEventListener("change", () => save());
  }
});
$("#language").addEventListener("change", () => save());
$$(".seg button").forEach((b) => b.addEventListener("click", () => {
  b.parentElement.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
  save();
}));

$("#ask").addEventListener("click", () => post({ type: "ask" }));
$("#import").addEventListener("click", () => post({ type: "import" }));
$$("[data-test]").forEach((b) => b.addEventListener("click", (e) => { e.preventDefault(); KediSound[b.dataset.test](); }));

$("#decks").addEventListener("change", (e) => {
  const g = e.target.dataset.g;
  if (g) post({ type: "toggle_deck", name: g, on: e.target.checked });
});
$("#decks").addEventListener("click", async (e) => {
  const file = e.target.closest("[data-del]")?.dataset.del;
  if (!file) return;
  const d = state.decks.find((x) => x.file === file);
  if (await confirmBox(t("confirm_delete", { name: d ? d.name : file }))) post({ type: "delete_deck", name: file });
});
$("#reset").addEventListener("click", async () => {
  if (await confirmBox(t("confirm_reset"))) post({ type: "reset_progress" });
});

applyI18n();

/* opened directly in a browser: demo data */
if (!window.webkit || !window.webkit.messageHandlers) {
  window.setState({
    settings: { language: "auto", enabled: true, min_gap: 10, max_gap: 30, idle_limit: 3, mode: "smart", direction: "front", corner: "bottom-right", retire: true, retire_after: 3, sound_answer: true, sound_open: true, disabled_decks: [] },
    languages: { en: "English", tr: "Türkçe" },
    decks: [{ file: "german-basics.txt", name: "German basics", front: "Deutsch", back: "English", count: 60 }],
    stats: { correct: 12, wrong: 4, learned: 3, total: 60 },
    next_at: Date.now() / 1000 + 900, formats: [".txt", ".csv"],
  });
} else {
  post({ type: "ready" });
}
