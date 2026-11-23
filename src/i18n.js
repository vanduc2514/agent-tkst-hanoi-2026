// Minimal dependency-free i18n runtime for the static site. The catalogues live in
// i18n/vi.json and i18n/en.json; this file detects the visitor's language, keeps the
// choice in localStorage, translates the static markup through data-i18n attributes
// and exposes t()/vocab() for the strings the page builds in JavaScript.
(() => {
  "use strict";

  const SUPPORTED = ["vi", "en"];
  const DEFAULT_LOCALE = "vi";
  const STORAGE_KEY = "tkst:lang";
  const LOCALE_TAGS = { vi: "vi-VN", en: "en-GB" };
  const FILES = { vi: "i18n/vi.json", en: "i18n/en.json" };

  const catalogs = Object.create(null);
  const missing = new Set();
  let locale = DEFAULT_LOCALE;

  // Anything that is not English falls back to Vietnamese, which is the default.
  function normalize(value) {
    return String(value || "").toLowerCase().startsWith("en") ? "en" : DEFAULT_LOCALE;
  }

  function readStored() {
    try { return localStorage.getItem(STORAGE_KEY); } catch { return null; }
  }

  function writeStored(value) {
    try { localStorage.setItem(STORAGE_KEY, value); } catch { /* storage blocked */ }
  }

  function detect() {
    const fromUrl = new URLSearchParams(window.location.search).get("lang");
    if (fromUrl) return normalize(fromUrl);
    const stored = readStored();
    if (SUPPORTED.includes(stored)) return stored;
    const languages = navigator.languages?.length ? navigator.languages : [navigator.language];
    return normalize(languages[0]);
  }

  function lookup(catalog, key) {
    let node = catalog;
    for (const part of key.split(".")) {
      if (!node || typeof node !== "object") return undefined;
      node = node[part];
    }
    return typeof node === "string" ? node : undefined;
  }

  function interpolate(template, params) {
    return template.replace(/\{(\w+)\}/g, (match, name) =>
      Object.hasOwn(params, name) ? String(params[name]) : match);
  }

  function resolve(key, params) {
    const active = catalogs[locale] || {};
    const fallback = catalogs[DEFAULT_LOCALE] || {};
    const plural = typeof params.count === "number"
      ? new Intl.PluralRules(LOCALE_TAGS[locale] || locale).select(params.count)
      : null;
    const candidates = plural ? [`${key}.${plural}`, key] : [key];
    for (const candidate of candidates) {
      const value = lookup(active, candidate) ?? lookup(fallback, candidate);
      if (value !== undefined) return value;
    }
    return undefined;
  }

  function t(key, params = {}) {
    const template = resolve(key, params);
    if (template === undefined) {
      missing.add(key);
      return key;
    }
    return interpolate(template, params);
  }

  // Data vocabularies (venue kinds, clusters) are keyed by value rather than dotted
  // keys, so they need their own lookup instead of t().
  function vocab(group, value) {
    const table = (catalogs[locale] || {}).vocab?.[group];
    const fallback = (catalogs[DEFAULT_LOCALE] || {}).vocab?.[group];
    return table?.[value] || fallback?.[value] || value;
  }

  function applyAttributeSpec(element) {
    const spec = element.getAttribute("data-i18n-attr") || "";
    for (const entry of spec.split(";")) {
      const [attribute, key] = entry.split(":").map((part) => part.trim());
      if (attribute && key) element.setAttribute(attribute, t(key));
    }
  }

  function apply(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((element) => {
      element.textContent = t(element.getAttribute("data-i18n"));
    });
    root.querySelectorAll("[data-i18n-html]").forEach((element) => {
      element.innerHTML = t(element.getAttribute("data-i18n-html"));
    });
    root.querySelectorAll("[data-i18n-attr]").forEach(applyAttributeSpec);
  }

  function applyDocumentMeta() {
    const title = t("meta.title");
    if (title !== "meta.title") document.title = title;
    const description = document.querySelector('meta[name="description"]');
    const descriptionText = t("meta.description");
    if (description && descriptionText !== "meta.description") description.setAttribute("content", descriptionText);
    document.documentElement.lang = locale;
  }

  function setLocale(next, options = {}) {
    locale = SUPPORTED.includes(next) ? next : DEFAULT_LOCALE;
    if (options.persist !== false) writeStored(locale);
    applyDocumentMeta();
    apply();
    if (!options.silent) {
      document.dispatchEvent(new CustomEvent("i18n:change", { detail: { locale } }));
    }
    return locale;
  }

  async function load() {
    locale = detect();
    const entries = await Promise.all(Object.entries(FILES).map(async ([code, url]) => {
      const response = await fetch(url, { cache: "no-cache" });
      if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
      return [code, await response.json()];
    }));
    for (const [code, catalog] of entries) catalogs[code] = catalog;
    applyDocumentMeta();
    apply();
    return locale;
  }

  window.I18n = {
    load,
    t,
    vocab,
    apply,
    setLocale,
    detect,
    get locale() { return locale; },
    get localeTag() { return LOCALE_TAGS[locale] || locale; },
    get missing() { return [...missing]; }
  };
})();
