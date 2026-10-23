/* SpoolmanScale Pro - shared helpers: text, DOM, requests, dialogs.
 *
 * Everything the pages share lives on window.SSPro. Rules that keep the
 * pages safe and alike:
 *   - Text a person reads comes from t(key), never a literal in a page file.
 *   - Data from the server goes into the page as textContent (el() below),
 *     never through innerHTML.
 *   - Every request goes through api(): it adds the X-SSPro header the
 *     server demands for changes, and turns every failure into an error
 *     code the caller can translate.
 */
(function () {
  "use strict";

  const LANG_KEY = "sspro.lang";
  const TOAST_MS = 3500;
  const SUPPORTED = ["en", "de"];

  function pickLanguage() {
    let stored = null;
    try { stored = localStorage.getItem(LANG_KEY); } catch (e) { /* private mode */ }
    if (stored && SUPPORTED.includes(stored)) return stored;
    const browser = (navigator.language || "en").slice(0, 2).toLowerCase();
    return SUPPORTED.includes(browser) ? browser : "en";
  }

  const lang = pickLanguage();
  document.documentElement.lang = lang;

  function setLanguage(code) {
    try { localStorage.setItem(LANG_KEY, code); } catch (e) { /* stays for this load */ }
    location.reload();
  }

  // English is the fallback for a key a translation does not have yet.
  function t(key, vars) {
    const table = window.SSPRO_I18N || {};
    let text = (table[lang] && table[lang][key]) || (table.en && table.en[key]) || key;
    if (vars) {
      for (const name of Object.keys(vars)) text = text.split("{" + name + "}").join(String(vars[name]));
    }
    return text;
  }

  // el("div", {class: "row"}, child, "text", ...): builds a node. Strings
  // become text nodes, so nothing passed here is ever parsed as markup.
  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(attrs || {})) {
      if (value === null || value === undefined || value === false) continue;
      if (name === "class") node.className = value;
      else if (name === "text") node.textContent = value;
      else if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
      else node.setAttribute(name, value === true ? "" : value);
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function $(selector, root) { return (root || document).querySelector(selector); }

  // Resolves to the parsed body ({ok: true, ...}); rejects with an Error
  // whose .code is the server's error code, or "network" / "bad_answer".
  async function api(path, options) {
    const opts = Object.assign({ method: "GET" }, options || {});
    const headers = { "X-SSPro": "1" };
    if (opts.body !== undefined && !(opts.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    opts.headers = headers;
    opts.credentials = "same-origin";
    let response;
    try {
      response = await fetch(path, opts);
    } catch (e) {
      throw Object.assign(new Error("network"), { code: "network" });
    }
    let data;
    try {
      data = await response.json();
    } catch (e) {
      throw Object.assign(new Error("bad_answer"), { code: "bad_answer", status: response.status });
    }
    if (!data.ok) {
      if (data.error === "login_required") document.dispatchEvent(new CustomEvent("sspro:logout"));
      throw Object.assign(new Error(data.error), { code: data.error, status: response.status, data: data });
    }
    return data;
  }

  function errorText(error) {
    const code = (error && error.code) || "internal_error";
    const key = "err." + code;
    const text = t(key);
    return text === key ? t("err.unknown", { code: code }) : text;
  }

  let toastTimer = null;
  function toast(text, bad) {
    let node = $(".toast");
    if (!node) {
      node = el("div", { class: "toast", role: "status", "aria-live": "polite" });
      document.body.append(node);
    }
    node.textContent = text;
    node.classList.toggle("bad", !!bad);
    node.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { node.hidden = true; }, TOAST_MS);
  }

  // A yes/no question in a <dialog>. Resolves true for the confirm button.
  function ask(title, text, confirmLabel, danger) {
    return new Promise((resolve) => {
      const dialog = el("dialog", {});
      const finish = (answer) => { dialog.close(); dialog.remove(); resolve(answer); };
      dialog.append(
        el("h3", { text: title }),
        el("p", { text: text }),
        el("div", { class: "btnrow" },
          el("button", { class: "quiet", type: "button", onclick: () => finish(false) }, t("common.cancel")),
          el("button", { class: danger ? "danger" : "", type: "button", onclick: () => finish(true) }, confirmLabel)));
      dialog.addEventListener("cancel", (e) => { e.preventDefault(); finish(false); });
      document.body.append(dialog);
      dialog.showModal();
    });
  }

  // Runs fn while button shows it is busy; reports a failure as a toast.
  async function busy(button, fn) {
    button.disabled = true;
    try {
      return await fn();
    } catch (e) {
      toast(errorText(e), true);
      return undefined;
    } finally {
      button.disabled = false;
    }
  }

  function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) return "-";
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (days) return t("fmt.days_hours", { d: days, h: hours });
    if (hours) return t("fmt.hours_minutes", { h: hours, m: minutes });
    return t("fmt.minutes", { m: minutes });
  }

  function formatClock(epochSeconds) {
    return new Date(epochSeconds * 1000).toLocaleString(lang, { dateStyle: "medium", timeStyle: "medium" });
  }

  window.SSPro = { lang, setLanguage, t, el, $, api, errorText, toast, ask, busy, formatDuration, formatClock, pages: {} };
})();
