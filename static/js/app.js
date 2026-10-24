/* SpoolmanScale Pro - start-up, login gate and page switching.
 *
 * A page is an object in SSPro.pages with
 *   nav:     the i18n key of its tab
 *   render:  function (container) that draws it and returns a cleanup
 *            function (stops its timers) or nothing.
 *   visible: optional, function (system) deciding from /api/system
 *            whether the page is offered at all (the demo page only
 *            where demo mode is enabled).
 *   hidden:  optional; reachable by its #name but not in the navigation
 *            (the setup assistant).
 * The order of PAGE_ORDER is the order of the tabs. A page file only
 * registers itself; this file decides when it is shown.
 */
(function () {
  "use strict";
  const { t, el, $, api, errorText } = SSPro;

  const PAGE_ORDER = ["overview", "scaleview", "demo", "backup", "updates", "scale", "network", "system", "setup"];
  const DEFAULT_PAGE = "overview";
  let cleanup = null;

  // address: the Pi's own (/api/system), shown next to the version unless
  // the page was opened by it anyway.
  function header(subline, address) {
    const version = "v" + document.documentElement.dataset.version;
    const second = address && address !== location.hostname ? address + " · " + version : version;
    return el("header", { class: "head" },
      el("div", { class: "mark" }, el("img", { src: "/static/img/logo.jpg", alt: "" })),
      el("div", {},
        el("div", { class: "wordmark" }, "SpoolmanScale ", el("span", { text: "Pro" })),
        el("div", { class: "subline", text: subline })),
      el("div", { class: "addr" },
        el("b", { text: location.host }),
        el("i", { text: second })));
  }

  function offered(system) {
    return PAGE_ORDER.filter((n) => SSPro.pages[n] && (!SSPro.pages[n].visible || SSPro.pages[n].visible(system)));
  }

  function currentPage(pages) {
    const name = location.hash.replace("#", "");
    return pages.includes(name) ? name : DEFAULT_PAGE;
  }

  function nav(pages, active) {
    const links = pages.filter((name) => !SSPro.pages[name].hidden).map((name) =>
      el("a", { href: "#" + name, class: name === active ? "on" : "" }, t(SSPro.pages[name].nav)));
    // Nothing to log out of without a password.
    const logout = authMode !== "password" ? null
      : el("a", { href: "#", onclick: (e) => { e.preventDefault(); logOut(); } }, t("nav.logout"));
    return el("nav", { class: "nav" }, links, el("span", { class: "spacer" }), logout);
  }

  async function showPage() {
    if (cleanup) { cleanup(); cleanup = null; }
    let system = {};
    let settings = {};
    try {
      [system, settings] = await Promise.all([api("/api/system"), api("/api/settings")]);
    } catch (e) {
      if (e.code === "login_required") return;  // the gate is already up
    }
    // A Pi not set up yet starts in the assistant, once it is asked for no
    // other page by its address.
    if (settings.settings && !settings.settings.setup_done && !location.hash) {
      history.replaceState(null, "", "#setup");
    }
    const pages = offered(system);
    const name = currentPage(pages);
    const main = el("main", { class: "wrap" });
    const app = $("#app");
    app.replaceChildren(el("div", { class: "wrap" }, header(t("app.tagline"), system.address), nav(pages, name)), main,
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
