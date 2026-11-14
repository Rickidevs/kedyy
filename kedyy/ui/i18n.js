"use strict";
/* Interface strings are injected by the app as window.I18N (see kedyy/i18n.py). */
window.I18N = window.I18N || {};
function t(key, vars = {}) {
  const s = window.I18N[key];
  if (s == null) return key;
  return String(s).replace(/\{(\w+)\}/g, (_, n) => (vars[n] ?? ""));
}
function tlist(key) {
  const a = window.I18N[key];
  return Array.isArray(a) && a.length ? a : [t(key)];
}
function applyI18n(root = document) {
  document.documentElement.lang = window.I18N._code || "en";
  root.querySelectorAll("[data-t]").forEach((el) => (el.textContent = t(el.dataset.t)));
  root.querySelectorAll("[data-t-title]").forEach((el) => (el.title = t(el.dataset.tTitle)));
  root.querySelectorAll("[data-t-ph]").forEach((el) => (el.placeholder = t(el.dataset.tPh)));
}
