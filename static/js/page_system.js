/* SpoolmanScale Pro - the Pi itself: look of the page, password, restart
 * and shutdown.
 */
(function () {
  "use strict";
  const { t, el, api, ask, busy, toast, errorText } = SSPro;

  const THEME_KEY = "sspro.theme";
  const THEMES = ["system", "dark", "light"];
  const LANGUAGES = ["en", "de"];

  function storedTheme() {
    try { return localStorage.getItem(THEME_KEY) || "system"; } catch (e) { return "system"; }
  }

  function applyTheme(theme) {
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
  }

  function select(options, current, labelOf, onChange) {
    const node = el("select", {}, options.map((o) => el("option", { value: o, selected: o === current }, labelOf(o))));
    node.addEventListener("change", () => onChange(node.value));
    return node;
  }

  function lookCard() {
    const language = select(LANGUAGES, SSPro.lang, (code) => t("lang." + code), SSPro.setLanguage);
    const theme = select(THEMES, storedTheme(), (name) => t("theme." + name), (value) => {
      try { localStorage.setItem(THEME_KEY, value); } catch (e) { /* this load only */ }
      applyTheme(value);
    });
    return el("section", { class: "card" }, el("h2", { text: t("look.title") }),
      el("div", { class: "field" }, el("label", { text: t("look.language") }), language),
      el("div", { class: "field" }, el("label", { text: t("look.theme") }), theme),
      el("p", { class: "note", text: t("look.note") }));
  }

  function passwordCard() {
    const current = el("input", { type: "password", autocomplete: "current-password" });
    const next = el("input", { type: "password", autocomplete: "new-password" });
    const message = el("div", { class: "msg", role: "status" });
    const save = el("button", { type: "button" }, t("password.change"));
    save.addEventListener("click", () => busy(save, async () => {
      try {
        await api("/api/auth/password", { method: "POST", body: { current: current.value, new: next.value } });
        current.value = next.value = "";
        message.className = "msg";
        message.textContent = t("password.changed");
      } catch (e) {
        message.className = "msg bad";
        message.textContent = errorText(e);
      }
    }));
    return el("section", { class: "card" }, el("h2", { text: t("password.title") }),
      el("div", { class: "field" }, el("label", { text: t("password.current") }), current),
      el("div", { class: "field" }, el("label", { text: t("password.new") }), next,
        el("p", { class: "hint", text: t("password.hint") })),
      el("div", { class: "btnrow" }, save), message);
  }

  function powerButton(labelKey, path, danger) {
    const button = el("button", { type: "button", class: danger ? "danger" : "quiet" }, t(labelKey));
    button.addEventListener("click", async () => {
      if (!(await ask(t(labelKey), t(labelKey + "_text"), t(labelKey), danger))) return;
      await busy(button, async () => {
        await api(path, { method: "POST" });
        toast(t(labelKey + "_started"));
      });
    });
    return button;
  }

  function powerCard(system) {
    return el("section", { class: "card" }, el("h2", { text: t("power.title") }),
      el("div", { class: "rows" },
        el("div", { class: "row" }, el("span", { class: "k", text: t("power.version") }), el("span", { class: "v mono", text: system.version })),
        el("div", { class: "row" }, el("span", { class: "k", text: t("power.hostname") }), el("span", { class: "v mono", text: system.hostname }))),
      el("div", { class: "btnrow" }, powerButton("power.reboot", "/api/system/reboot", false),
        powerButton("power.poweroff", "/api/system/poweroff", true)),
      el("p", { class: "note", text: t("power.note") }));
  }

  function render(main) {
    const grid = el("div", { class: "grid" });
    main.append(grid);
    api("/api/system").then((system) => {
      grid.replaceChildren(lookCard(), passwordCard(), powerCard(system));
    }).catch((e) => { if (e.code !== "login_required") toast(errorText(e), true); });
  }

  // Before the first paint of any page, not only this one.
  applyTheme(storedTheme());
  SSPro.pages.system = { nav: "nav.system", render };
})();
