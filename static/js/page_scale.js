/* SpoolmanScale Pro - pairing the scale: where it is, its web password,
 * and what has to be set on the scale once so the Pi can switch it.
 */
(function () {
  "use strict";
  const { t, el, api, busy, toast, errorText } = SSPro;

  const DEFAULT_SCALE_NAME = "spoolmanscale.local";

  function pairingCard(settings, onSaved) {
    const address = el("input", { type: "text", value: settings.scale_address, placeholder: DEFAULT_SCALE_NAME, autocomplete: "off", spellcheck: "false" });
    const password = el("input", { type: "password", inputmode: "numeric", autocomplete: "off",
      placeholder: t(settings.scale_password_set ? "pair.password_kept" : "pair.password_none") });
    const result = el("div", { class: "msg", role: "status" });
    const save = el("button", { type: "button" }, t("pair.save_test"));
    save.addEventListener("click", () => busy(save, async () => {
      const body = { scale_address: address.value };
      if (password.value) body.scale_password = password.value;
      try {
        await api("/api/settings", { method: "POST", body: body });
      } catch (e) {
        result.className = "msg bad";
        result.textContent = errorText(e.code === "invalid_fields" ? { code: "pair_" + e.data.fields[0] } : e);
        return;
      }
      password.value = "";
      const scale = (await api("/api/scale")).scale;
      result.className = "msg" + (scale.paired && !scale.reachable ? " bad" : "");
      result.textContent = !scale.paired ? t("pair.removed")
        : scale.reachable ? t("pair.ok", { version: scale.version, backend: scale.backend })
          : errorText({ code: scale.error });
      onSaved();
    }));
    const forget = el("button", { type: "button", class: "quiet", disabled: !settings.scale_password_set }, t("pair.forget_password"));
    forget.addEventListener("click", () => busy(forget, async () => {
      await api("/api/settings", { method: "POST", body: { scale_password: "" } });
      toast(t("pair.password_forgotten"));
      onSaved();
    }));
    return el("section", { class: "card" },
      el("h2", { text: t("pair.title") }),
      el("div", { class: "field" }, el("label", { text: t("pair.address") }), address,
        el("p", { class: "hint", text: t("pair.address_hint") })),
      el("div", { class: "field" }, el("label", { text: t("pair.password") }), password,
        el("p", { class: "hint", text: t("pair.password_hint") })),
      el("div", { class: "btnrow" }, save, forget), result);
  }

  function setupCard(piName, backends) {
    const addresses = el("div", { class: "rows" }, backends.map((b) =>
      el("div", { class: "row" }, el("span", { class: "k", text: b.label }),
        el("span", { class: "v mono", text: piName + ":" + b.port }))));
    return el("section", { class: "card" },
      el("h2", { text: t("setup.title") }),
      el("ol", { class: "numbered" },
        el("li", { text: t("setup.step_share") }),
        el("li", {}, t("setup.step_addresses"), addresses),
        el("li", { text: t("setup.step_keys") }),
        el("li", { text: t("setup.step_done") })));
  }

  function render(main) {
    const grid = el("div", { class: "grid" });
    main.append(grid);
    const draw = async () => {
      try {
        const [settings, system, backends] = await Promise.all([
          api("/api/settings"), api("/api/system"), api("/api/backends")]);
        const piName = system.hostname.replace(/\.local$/, "") + ".local";
        grid.replaceChildren(pairingCard(settings.settings, draw), setupCard(piName, backends.backends));
      } catch (e) {
        if (e.code !== "login_required") toast(errorText(e), true);
      }
    };
    draw();
  }

  SSPro.pages.scale = { nav: "nav.scale", render };
})();
