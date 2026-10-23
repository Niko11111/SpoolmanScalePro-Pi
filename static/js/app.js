/* SpoolmanScale Pro - start-up, login gate and page switching.
 *
 * A page is an object in SSPro.pages with
 *   nav:    the i18n key of its tab
 *   render: function (container) that draws it and returns a cleanup
 *           function (stops its timers) or nothing.
 * The order of PAGE_ORDER is the order of the tabs. A page file only
 * registers itself; this file decides when it is shown.
 */
(function () {
  "use strict";
  const { t, el, $, api, errorText } = SSPro;

  const PAGE_ORDER = ["overview", "scale", "system"];
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

  function currentPage() {
    const name = location.hash.replace("#", "");
    return PAGE_ORDER.includes(name) && SSPro.pages[name] ? name : DEFAULT_PAGE;
  }

  function nav(active) {
    const links = PAGE_ORDER.filter((n) => SSPro.pages[n]).map((name) =>
      el("a", { href: "#" + name, class: name === active ? "on" : "" }, t(SSPro.pages[name].nav)));
    const logout = el("a", { href: "#", onclick: (e) => { e.preventDefault(); logOut(); } }, t("nav.logout"));
    return el("nav", { class: "nav" }, links, el("span", { class: "spacer" }), logout);
  }

  function showPage() {
    if (cleanup) { cleanup(); cleanup = null; }
    const name = currentPage();
    const main = el("main", { class: "wrap" });
    const app = $("#app");
    app.replaceChildren(el("div", { class: "wrap" }, header(t("app.tagline")), nav(name)), main,
      el("footer", { class: "foot" }, t("app.footer")));
    cleanup = SSPro.pages[name].render(main) || null;
  }

  async function logOut() {
    try { await api("/api/auth/logout", { method: "POST" }); } catch (e) { /* gone either way */ }
    showGate(true);
  }

  // First visit sets the password; later visits log in with it.
  function showGate(passwordSet) {
    if (cleanup) { cleanup(); cleanup = null; }
    const input = el("input", { type: "password", autocomplete: passwordSet ? "current-password" : "new-password", required: true });
    const message = el("div", { class: "msg bad", role: "alert" });
    const submit = el("button", { class: "block", type: "submit" }, t(passwordSet ? "gate.login" : "gate.set"));
    const form = el("form", { class: "card" },
      el("h2", { text: t(passwordSet ? "gate.login_title" : "gate.setup_title") }),
      passwordSet ? null : el("p", { class: "hint", text: t("gate.setup_hint") }),
      el("div", { class: "field" }, el("label", { text: t("gate.password") }), input),
      message, submit);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      submit.disabled = true;
      try {
        await api(passwordSet ? "/api/auth/login" : "/api/auth/setup", { method: "POST", body: { password: input.value } });
        showPage();
      } catch (err) {
        message.textContent = errorText(err);
        submit.disabled = false;
      }
    });
    $("#app").replaceChildren(el("div", { class: "gate" }, header(t("app.tagline")), form));
    input.focus();
  }

  async function start() {
    try {
      const state = await api("/api/auth/state");
      if (state.logged_in) showPage(); else showGate(state.password_set);
    } catch (e) {
      $("#app").replaceChildren(el("div", { class: "card gate" }, el("p", { class: "msg bad", text: errorText(e) })));
    }
  }

  window.addEventListener("hashchange", showPage);
  document.addEventListener("sspro:logout", () => showGate(true));
  start();
})();
