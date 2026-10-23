/* SpoolmanScale Pro - pairing the scale (found on the network or typed in),
 * its web password, and entering this Pi as the server of every backend
 * on the scale with one button (scale_setup.py).
 */
(function () {
  "use strict";
  const { t, el, api, ask, busy, toast, errorText, views } = SSPro;

  const DEFAULT_SCALE_NAME = "spoolmanscale.local";

  async function saveAndTest(address, password, result, onSaved) {
    const body = { scale_address: address };
    if (password) body.scale_password = password;
    try {
      await api("/api/settings", { method: "POST", body: body });
    } catch (e) {
      result.className = "msg bad";
      result.textContent = errorText(e.code === "invalid_fields" ? { code: "pair_" + e.data.fields[0] } : e);
      return;
    }
    const scale = (await api("/api/scale")).scale;
    result.className = "msg" + (scale.paired && !scale.reachable ? " bad" : "");
    result.textContent = !scale.paired ? t("pair.removed")
      : scale.reachable ? t("pair.ok", { version: scale.version, backend: scale.backend })
        : errorText({ code: scale.error });
    onSaved();
  }

  function foundList(scales, pick) {
    if (!scales.length) return [el("p", { class: "hint", text: t("pair.none_found") })];
    return scales.map((s) => el("div", { class: "listrow" },
      el("div", {}, el("div", { class: "nm", text: s.name }),
        el("div", { class: "sz", text: s.host + " - " + s.address + " - " + s.firmware + " - " + s.backend })),
      el("button", { type: "button", onclick: () => pick(s) }, t("pair.take"))));
  }

  function pairingCard(settings, onSaved) {
    const address = el("input", { type: "text", value: settings.scale_address, placeholder: DEFAULT_SCALE_NAME, autocomplete: "off", spellcheck: "false" });
    const password = el("input", { type: "password", inputmode: "numeric", autocomplete: "off",
      placeholder: t(settings.scale_password_set ? "pair.password_kept" : "pair.password_none") });
    const result = el("div", { class: "msg", role: "status" });
    const found = el("div", { class: "wrap" });
    const save = el("button", { type: "button" }, t("pair.save_test"));
    save.addEventListener("click", () => busy(save, () => saveAndTest(address.value, password.value, result, onSaved)));
    const search = el("button", { type: "button", class: "quiet" }, t("pair.search"));
    search.addEventListener("click", () => busy(search, async () => {
      found.replaceChildren(el("p", { class: "hint", text: t("pair.searching") }));
      const scales = (await api("/api/scale/discover", { method: "POST" })).scales;
      found.replaceChildren(...foundList(scales, (s) => {
        address.value = s.host;
        busy(save, () => saveAndTest(s.host, password.value, result, onSaved));
      }));
    }));
    const forget = el("button", { type: "button", class: "quiet", disabled: !settings.scale_password_set }, t("pair.forget_password"));
    forget.addEventListener("click", () => busy(forget, async () => {
      await api("/api/settings", { method: "POST", body: { scale_password: "" } });
      toast(t("pair.password_forgotten"));
      onSaved();
    }));
    return el("section", { class: "card" },
      el("h2", {}, el("span", { text: t("pair.title") }), search), found,
      el("div", { class: "field" }, el("label", { text: t("pair.address") }), address,
        el("p", { class: "hint", text: t("pair.address_hint") })),
      el("div", { class: "field" }, el("label", { text: t("pair.password") }), password,
        el("p", { class: "hint", text: t("pair.password_hint") })),
      el("div", { class: "btnrow" }, save, forget), result);
  }

  function addressResults(addresses, labelOf) {
    return el("div", { class: "rows" }, Object.entries(addresses).map(([key, r]) =>
      el("div", { class: "row" }, el("span", { class: "k", text: labelOf(key) }),
        el("span", { class: "v" }, el("span", { class: "mono", text: r.address + " " }),
          el("span", { class: "pill " + (r.ok ? "ok" : "off") }, t(r.ok ? "setup.reached" : "setup.stored"))))));
  }

  function setupCard(piName, labelOf, paired) {
    const jobSlot = el("div", { class: "wrap" });
    const resultSlot = el("div", { class: "wrap" });
    const useIp = el("input", { type: "checkbox" });
    const run = el("button", { type: "button", disabled: !paired }, t("setup.run"));
    let unfollow = null;
    run.addEventListener("click", async () => {
      if (!(await ask(t("setup.run"), t("setup.run_text"), t("setup.run")))) return;
      await busy(run, async () => {
        resultSlot.replaceChildren();
        await api("/api/scale/setup", { method: "POST", body: { use_ip: useIp.checked } });
        if (unfollow) unfollow();
        unfollow = views.followJob(jobSlot, () => t("setup.the_scale"), (job) => {
          if (job.ok) resultSlot.replaceChildren(addressResults(job.result.addresses, labelOf), el("p", { class: "note", text: t("setup.result_note") }));
        }, false);
      });
    });
    return el("section", { class: "card" },
      el("h2", { text: t("setup.title") }),
      el("ol", { class: "numbered" },
        el("li", { text: t("setup.step_share") }),
        el("li", {}, t("setup.step_auto", { name: piName }),
          el("label", { class: "check" }, el("span", { text: t("setup.use_ip") }), el("span", { class: "switch" }, useIp, el("i", {}))),
          el("div", { class: "btnrow" }, run), jobSlot, resultSlot),
        el("li", { text: t("setup.step_keys") })));
  }

  function render(main) {
    const grid = el("div", { class: "grid" });
    main.append(grid);
    const draw = async () => {
      try {
        const [settings, system, backends] = await Promise.all([
          api("/api/settings"), api("/api/system"), api("/api/backends")]);
        const piName = system.hostname.replace(/\.local$/, "") + ".local";
        grid.replaceChildren(pairingCard(settings.settings, draw),
          setupCard(piName, views.labelsFrom(backends.backends), !!settings.settings.scale_address));
      } catch (e) {
        if (e.code !== "login_required") toast(errorText(e), true);
      }
    };
    draw();
  }

  SSPro.pages.scale = { nav: "nav.scale", render };
})();
