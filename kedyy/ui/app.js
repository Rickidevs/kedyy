"use strict";

const $ = (s) => document.querySelector(s);
const cat = $("#cat");
const IDLE_MS = 2 * 60 * 1000;          // close after 2 minutes without interaction
const AUTO_CLOSE_OK_MS = 9000;           // after a correct answer, leave by itself after 9 s


let q = null;
let answered = false;
let closing = false;
let idleTimer = null;
let autoTimer = null;

const pick = (a) => a[Math.floor(Math.random() * a.length)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function post(msg) {
  try { window.webkit.messageHandlers.kedi.postMessage(JSON.stringify(msg)); }
  catch (e) { console.log("post", msg); }
}

function say(text, ms = 2600) {
  const b = $("#bubble");
  b.textContent = text;
  b.classList.add("show");
  clearTimeout(say._t);
  if (ms) say._t = setTimeout(() => b.classList.remove("show"), ms);
}

function mood(m) {
  cat.classList.remove("happy", "sad", "wave");
  if (m) cat.classList.add(m);
}

function resetIdle() {
  clearTimeout(idleTimer);
  idleTimer = setTimeout(() => close(answered ? "done" : "timeout"), IDLE_MS);
}

function renderStats() {
  $("#stats").textContent = t("stats_line", q.stats);
}
const longest = (a) => a.reduce((x, y) => (y.length > x.length ? y : x), "");

/* ---------- called from Python ---------- */
window.showQuestion = function (data) {
  q = data;
  answered = false;
  closing = false;
  applyI18n();
  $("#phrase").textContent = q.shown;
  $("#source").textContent = q.deck;
  const L = q.labels || {};
  $("#prompt").textContent = q.direction === "front"
    ? (L.prompt || (L.front && L.back ? `${L.front} → ${L.back}` : t("prompt_front")))
    : (L.front && L.back ? `${L.back} → ${L.front}` : t("prompt_back"));
  $("#hint").innerHTML = esc(t("hint_pick", { keys: "%K%" })).replace("%K%", "<kbd>1</kbd>–<kbd>4</kbd>");
  renderStats();
  $("#options").innerHTML = q.options.map((o, i) =>
    `<button class="opt" data-i="${i}"><span class="num">${i + 1}</span><span class="txt">${esc(o.text)}</span></button>`
  ).join("");
  $("#options").querySelectorAll(".opt").forEach((b) => b.addEventListener("click", () => answer(+b.dataset.i)));
  $("#feedback").hidden = true;
  $("#btn-close").hidden = true;
  $("#btn-later").hidden = false;
  mood(null);
  $("#card").style.minHeight = "";
  reportSize();
};

/* Called by Python once the window is visible */
window.enter = function () {
  // the window has its real width now: measure the answered state (card still invisible)
  reserveHeight();
  reportSize();
  document.body.classList.remove("out");
  document.body.classList.add("in");
  setTimeout(() => say(q && q.all_done ? t("all_done") : pick(tlist("hello")), q && q.all_done ? 3500 : 2600), 900);
  if (q && q.sound_open) setTimeout(() => { try { KediSound.open(); } catch (e) {} }, 500);
  resetIdle();
};

/* ---------- explanation text ---------- */
function explainHTML(i) {
  let html = `<b>${esc(q.front)}</b> → ${esc(q.back)}`;
  if (i !== q.answer) {
    const mine = q.options[i];
    html += `<div class="note">${esc(t("your_choice", { mine: mine.text, other: mine.other }))}</div>`;
  }
  if (q.note) html += `<div class="note">💡 ${esc(q.note)}</div>`;
  return html;
}

/* Measure the tallest answered state in advance and open the card at that height,
   so the window doesn't grow and jump when you answer. */
function reserveHeight() {
  const card = $("#card"), fb = $("#feedback");
  card.style.minHeight = "";
  document.querySelectorAll(".opt").forEach((b, j) => {
    if (j !== q.answer) b.querySelector(".txt").insertAdjacentHTML("beforeend", `<span class="en tmp">= ${esc(q.options[j].other)}</span>`);
  });
  $("#hint").hidden = true;
  fb.hidden = false;
  let max = 0;
  for (let i = 0; i < q.options.length; i++) {
    $("#verdict").textContent = i === q.answer ? longest(tlist("praise")) : t("wrong_verdict");
    $("#explain").innerHTML = explainHTML(i);
    max = Math.max(max, card.offsetHeight);
  }
  document.querySelectorAll(".en.tmp").forEach((e) => e.remove());
  fb.hidden = true;
  $("#verdict").textContent = "";
  $("#explain").innerHTML = "";
  $("#hint").hidden = false;
  card.style.minHeight = max + "px";
}

/* ---------- answer ---------- */
function answer(i) {
  if (answered || closing || !q) return;
  answered = true;
  resetIdle();
  const ok = i === q.answer;
  const btns = [...document.querySelectorAll(".opt")];
  btns.forEach((b, j) => {
    b.disabled = true;
    const o = q.options[j];
    if (j !== q.answer) b.querySelector(".txt").insertAdjacentHTML("beforeend", `<span class="en">= ${esc(o.other)}</span>`);
    if (j === q.answer) b.classList.add("correct");
    else if (j === i) b.classList.add("wrong");
    else b.classList.add("dim");
  });

  const fb = $("#feedback");
  fb.className = ok ? "ok" : "bad";
  $("#verdict").textContent = ok ? pick(tlist("praise")) : t("wrong_verdict");
  $("#explain").innerHTML = explainHTML(i);
  $("#hint").hidden = true;
  fb.hidden = false;

  $("#btn-later").hidden = true;
  const close_btn = $("#btn-close");
  close_btn.hidden = false;
  close_btn.textContent = ok ? t("close") : t("got_it");

  if (q.sound_answer) { try { ok ? KediSound.ok() : KediSound.bad(); } catch (e) {} }
  if (ok) {
    mood("happy");
    cat.classList.remove("jump"); void cat.offsetWidth; cat.classList.add("jump");
    hearts(); confetti();
    say(pick(tlist("praise")));
    autoTimer = setTimeout(() => close("done"), AUTO_CLOSE_OK_MS);
  } else {
    mood("sad");
    say(pick(tlist("cheer_up")), 3200);
  }
  ok ? q.stats.correct++ : q.stats.wrong++;
  renderStats();
  post({ type: "answer", id: q.id, correct: ok });
  reportSize();
}

/* ---------- closing ---------- */
function close(reason) {
  if (closing) return;
  closing = true;
  clearTimeout(idleTimer); clearTimeout(autoTimer);
  mood("wave");
  say(pick(tlist("bye")), 0);
  setTimeout(() => {
    $("#bubble").classList.remove("show");
    document.body.classList.remove("in");
    document.body.classList.add("out");
  }, 1300);
  setTimeout(() => post({ type: "closed", reason }), 1300 + 650);
}

$("#btn-later").addEventListener("click", () => close("later"));
$("#btn-close").addEventListener("click", () => close("done"));

document.addEventListener("keydown", (e) => {
  resetIdle();
  if (e.key === "Escape") return close(answered ? "done" : "later");
  if (!answered && /^[1-4]$/.test(e.key)) return answer(+e.key - 1);
  if (answered && (e.key === "Enter" || e.key === " ")) return close("done");
});
["mousemove", "mousedown"].forEach((ev) => document.addEventListener(ev, () => {
  resetIdle();
  if (answered && autoTimer) { clearTimeout(autoTimer); autoTimer = setTimeout(() => close("done"), AUTO_CLOSE_OK_MS); }
}, { passive: true }));

/* ---------- effects ---------- */
function catCenter() {
  const r = $("#catwrap").getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height * 0.45 };
}
function hearts() {
  const fx = $("#fx"), c = catCenter();
  const colors = ["#ff6b8a", "#ff8fa3", "#f08a3c", "#ffb84d"];
  for (let k = 0; k < 9; k++) {
    const h = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    h.setAttribute("viewBox", "0 0 24 24");
    h.classList.add("heart");
    h.innerHTML = `<path fill="${pick(colors)}" d="M12 21s-7.5-4.6-10-9.3C.3 8.3 2.4 4 6.4 4c2.3 0 3.9 1.3 5.6 3.3C13.7 5.3 15.3 4 17.6 4c4 0 6.1 4.3 4.4 7.7C19.5 16.4 12 21 12 21z"/>`;
    h.style.left = c.x - 9 + (Math.random() * 60 - 30) + "px";
    h.style.top = c.y - 9 + "px";
    h.style.setProperty("--dx", (Math.random() * 120 - 60) + "px");
    h.style.setProperty("--rot", (Math.random() * 60 - 30) + "deg");
    h.style.animationDelay = k * 70 + "ms";
    fx.appendChild(h);
    setTimeout(() => h.remove(), 2400);
  }
}
function confetti() {
  const fx = $("#fx"), c = catCenter();
  const colors = ["#f08a3c", "#2fb27a", "#4aa3ff", "#ffd34d", "#ff6b8a", "#a77bff"];
  for (let k = 0; k < 28; k++) {
    const d = document.createElement("div");
    d.className = "confetti";
    d.style.background = pick(colors);
    d.style.left = c.x + "px";
    d.style.top = c.y + "px";
    const ang = Math.random() * Math.PI * 2, dist = 60 + Math.random() * 120;
    d.style.setProperty("--dx", Math.cos(ang) * dist + "px");
    d.style.setProperty("--dy", Math.sin(ang) * dist * 0.6 + 80 + Math.random() * 80 + "px");
    d.style.setProperty("--rot", Math.random() * 720 - 360 + "deg");
    fx.appendChild(d);
    setTimeout(() => d.remove(), 1600);
  }
}

/* ---------- window size ---------- */
function reportSize() {
  post({ type: "size", h: Math.ceil($("#stage").getBoundingClientRect().height) });
}
new ResizeObserver(reportSize).observe($("#stage"));

/* Opened directly in a browser: show a demo question */
if (!window.webkit || !window.webkit.messageHandlers) {
  window.showQuestion({
    id: "demo", direction: "front", shown: "der Schmetterling", front: "der Schmetterling", back: "the butterfly",
    deck: "German basics", labels: { front: "Deutsch", back: "English" }, note: "plural: die Schmetterlinge", answer: 2,
    options: [
      { text: "the bridge", other: "die Brücke" },
      { text: "the glove", other: "der Handschuh" },
      { text: "the butterfly", other: "der Schmetterling" },
      { text: "the squirrel", other: "das Eichhörnchen" },
    ],
    stats: { correct: 12, wrong: 4, learned: 7, total: 120 },
  });
  window.enter();
}
