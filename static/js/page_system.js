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

  function input(type, autocomplete, value) {
    return el("input", { type: type, autocomplete: autocomplete, value: value || "" });
  }

  function labelled(labelKey, node, hintKey) {
    return el("div", { class: "field" }, el("label", { text: t(labelKey) }), node,
      hintKey ? el("p", { class: "hint", text: t(hintKey) }) : null);
  }

  async function post(path, body, message) {
    try {
      await api(path, { method: "POST", body: body });
      toast(t("account.saved"));
      SSPro.restart();
    } catch (e) {
      message.textContent = errorText(e);
    }
  }

  // Password mode: change name and password, or switch the login off.
  function protectedAccount(account) {
    const current = input("password", "current-password");
    const user = input("text", "username", account.username);
    const next = input("password", "new-password");
    const message = el("div", { class: "msg bad", role: "alert" });
    const save = el("button", { type: "button" }, t("account.save"));
    save.addEventListener("click", () => busy(save, () =>
      post("/api/auth/account", { current: current.value, username: user.value, password: next.value }, message)));
    const off = el("button", { type: "button", class: "danger" }, t("account.switch_off"));
    off.addEventListener("click", async () => {
      if (!(await ask(t("gate.open_title"), t("gate.open_text"), t("account.switch_off"), true))) return;
      await busy(off, () => post("/api/auth/open", { current: current.value }, message));
    });
    return [el("p", { class: "hint", text: t("account.signed_in", { name: account.username }) }),
      labelled("account.current", current, "account.current_hint"),
      labelled("gate.username", user), labelled("account.new_password", next, "account.password_hint"),
      el("div", { class: "btnrow" }, save, off), message];
  }

  // Open mode: the warning, and the way back to a login.
  function openAccount() {
    const user = input("text", "username", "admin");
    const next = input("password", "new-password");
    const message = el("div", { class: "msg bad", role: "alert" });
    const save = el("button", { type: "button" }, t("account.switch_on"));
    save.addEventListener("click", () => busy(save, () =>
      post("/api/auth/account", { username: user.value, password: next.value }, message)));
    return [el("div", { class: "callout bd", text: t("account.open_warning") }),
      labelled("gate.username", user), labelled("gate.password", next, "account.password_hint"),
      el("div", { class: "btnrow" }, save), message];
  }

  function accountCard() {
    const account = SSPro.account || { mode: "password", username: "" };
    return el("section", { class: "card" }, el("h2", { text: t("account.title") }),
      account.mode === "open" ? openAccount() : protectedAccount(account));
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
        powerButton("power.poweroff", "/api/system/poweroff", true),
        el("a", { class: "linkbtn", href: "#setup" }, t("setup.open"))),
      el("p", { class: "note", text: t("power.note") }));
  }

  // Several backends at once: what this Pi is, what that means, and the
  // owner's choice (backend_plan.py). Blocked on a small Pi.
  function capacityCard(plan) {
    const blocked = plan.rules.parallel === "blocked";
    const choice = plan.parallel_choice === null ? "auto" : plan.parallel_choice ? "on" : "off";
    const mode = el("select", { disabled: blocked }, ["auto", "on", "off"].map((v) =>
      el("option", { value: v, selected: v === choice }, t("cap.mode_" + v))));
    mode.addEventListener("change", async () => {
      const value = mode.value === "auto" ? null : mode.value === "on";
      try {
        await api("/api/settings", { method: "POST", body: { parallel_mode: value } });
        toast(t("account.saved"));
      } catch (e) {
        toast(errorText(e), true);
      }
    });
    return el("section", { class: "card" }, el("h2", { text: t("cap.title") }),
      el("div", { class: "rows" },
        el("div", { class: "row" }, el("span", { class: "k", text: t("cap.model") }), el("span", { class: "v", text: plan.model || "-" })),
        el("div", { class: "row" }, el("span", { class: "k", text: t("cap.ram") }), el("span", { class: "v mono", text: plan.ram_mb ? plan.ram_mb + " MB" : "-" }))),
      el("p", { class: "hint", text: t("cap.size_" + plan.rules.size) }),
      el("div", { class: "field" }, el("label", { text: t("cap.mode") }), mode));
  }

  function render(main) {
    const grid = el("div", { class: "grid" });
    const os = SSPro.views.osCard();
    const remote = SSPro.views.tailscaleCard();
    main.append(grid, os);
    Promise.all([api("/api/system"), api("/api/backends")]).then(([system, backends]) => {
      grid.replaceChildren(powerCard(system), capacityCard(backends.plan), accountCard(), lookCard(), remote);
    }).catch((e) => { if (e.code !== "login_required") toast(errorText(e), true); });
    return () => { os.stop(); remote.stop(); };
  }

  // Before the first paint of any page, not only this one.
  applyTheme(storedTheme());
  SSPro.pages.system = { nav: "nav.system", render };
})();
