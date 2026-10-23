/* SpoolmanScale Pro - start-up, login gate and page switching.
 *
 * A page is an object in SSPro.pages with
 *   nav:     the i18n key of its tab
 *   render:  function (container) that draws it and returns a cleanup
 *            function (stops its timers) or nothing.
 *   visible: optional, function (system) deciding from /api/system
 *            whether the page is offered at all (the demo page only
 *            where demo mode is enabled).
 * The order of PAGE_ORDER is the order of the tabs. A page file only
 * registers itself; this file decides when it is shown.
 */
(function () {
  "use strict";
  const { t, el, $, api, errorText } = SSPro;

  const PAGE_ORDER = ["overview", "scaleview", "demo", "backup", "updates", "scale", "network", "system"];
  const DEFAULT_PAGE = "overview";
  let cleanup = null;

  function header(subline) {
    return el("header", { class: "head" },
      el("div", { class: "mark" }, el("img", { src: "/static/img/logo.jpg", alt: "" })),
      el("div", {},
        el("div", { class: "wordmark" }, "SpoolmanScale ", el("span", { text: "Pro" })),
        el("div", { class: "subline", text: subline })),
      el("div", { class: "addr" },
        el("b", { text: location.host }),
        el("i", { text: "v" + document.documentElement.dataset.version })));
  }

  function offered(system) {
    return PAGE_ORDER.filter((n) => SSPro.pages[n] && (!SSPro.pages[n].visible || SSPro.pages[n].visible(system)));
  }

  function currentPage(pages) {
    const name = location.hash.replace("#", "");
    return pages.includes(name) ? name : DEFAULT_PAGE;
  }

  function nav(pages, active) {
    const links = pages.map((name) =>
      el("a", { href: "#" + name, class: name === active ? "on" : "" }, t(SSPro.pages[name].nav)));
    // Nothing to log out of without a password.
    const logout = authMode !== "password" ? null
      : el("a", { href: "#", onclick: (e) => { e.preventDefault(); logOut(); } }, t("nav.logout"));
    return el("nav", { class: "nav" }, links, el("span", { class: "spacer" }), logout);
  }

  async function showPage() {
    if (cleanup) { cleanup(); cleanup = null; }
    let system = {};
    try {
      system = await api("/api/system");
    } catch (e) {
      if (e.code === "login_required") return;  // the gate is already up
    }
    const pages = offered(system);
    const name = currentPage(pages);
    const main = el("main", { class: "wrap" });
    const app = $("#app");
    app.replaceChildren(el("div", { class: "wrap" }, header(t("app.tagline")), nav(pages, name)), main,
      el("footer", { class: "wrap" }, SSPro.views.linksRow(), el("p", { class: "foot", text: t("app.footer") })));
    cleanup = SSPro.pages[name].render(main) || null;
  }

  async function logOut() {
    try { await api("/api/auth/logout", { method: "POST" }); } catch (e) { /* gone either way */ }
    showGate(false);
  }

  // The account mode from /api/auth/state ("unset", "password", "open").
  let authMode = "password";

  function showGate(firstVisit) {
    if (cleanup) { cleanup(); cleanup = null; }
    const gate = SSPro.views.gateForm(firstVisit, start);
    $("#app").replaceChildren(el("div", { class: "gate" }, header(t("app.tagline")), gate.form));
    gate.focus.focus();
  }

  async function start() {
    try {
      const state = await api("/api/auth/state");
      authMode = state.mode;
      SSPro.account = { mode: state.mode, username: state.username };
      if (state.logged_in) showPage(); else showGate(state.mode === "unset");
    } catch (e) {
      $("#app").replaceChildren(el("div", { class: "card gate" }, el("p", { class: "msg bad", text: errorText(e) })));
    }
  }

  window.addEventListener("hashchange", showPage);
  document.addEventListener("sspro:logout", () => showGate(false));
  // For a page that changes the account mode (System).
  SSPro.restart = start;
  start();
})();
