/* SpoolmanScale Pro - the backend tiles and a backend's log.
 *
 * Pure drawing: takes what /api/backends and /api/job returned, gives back
 * nodes. The overview page owns the polling and passes onChange, which it
 * calls to refresh after an action.
 */
(function () {
  "use strict";
  const { t, el, api, ask, busy, toast } = SSPro;

  const LOGOS = {
    spoolman: "/static/img/spoolman-logo.svg",
    filaman: "/static/img/filaman-logo.ico",
    bambuddy: "/static/img/bambuddy-logo.png",
  };

  function backendUrl(backend) {
    return location.protocol + "//" + location.hostname + ":" + backend.port;
  }

  function statePill(backend) {
    if (backend.state === "running" && backend.ready) return el("span", { class: "pill ok" }, t("state.ready"));
    if (backend.state === "running") return el("span", { class: "pill wr busy" }, t("state.starting"));
    if (backend.state === "absent") return el("span", { class: "pill off" }, t("state.not_installed"));
    return el("span", { class: "pill off" }, t("state.stopped"));
  }

  async function activate(button, backend, all, onChange) {
    const current = all.find((b) => b.active);
    const text = current
      ? t("switch.confirm_text", { from: current.label, to: backend.label })
      : t("switch.confirm_first", { to: backend.label });
    if (!(await ask(t("switch.confirm_title", { to: backend.label }), text, t("switch.confirm_button")))) return;
    await busy(button, async () => {
      await api("/api/backends/" + backend.key + "/activate", { method: "POST" });
      onChange();
    });
  }

  // FilaMan's admin login, made by this Pi (backend_secrets.py): shown in a
  // dialog on request, never in the page itself.
  async function showFilamanLogin() {
    let login;
    try {
      login = (await api("/api/backends/filaman/login")).login;
    } catch (e) {
      toast(SSPro.errorText(e), true);
      return;
    }
    const dialog = el("dialog", {});
    const close = () => { dialog.close(); dialog.remove(); };
    dialog.append(el("h3", { text: t("login.title") }),
      el("div", { class: "rows" },
        el("div", { class: "row" }, el("span", { class: "k", text: t("login.email") }), el("span", { class: "v mono", text: login.email })),
        el("div", { class: "row" }, el("span", { class: "k", text: t("login.password") }), el("span", { class: "v mono", text: login.password }))),
      el("p", { class: "note", text: t("login.note") }),
      el("div", { class: "btnrow" }, el("button", { type: "button", onclick: close }, t("common.close"))));
    dialog.addEventListener("cancel", (e) => { e.preventDefault(); close(); });
    document.body.append(dialog);
    dialog.showModal();
  }

  function tile(backend, all, jobRunning, onChange, onLog) {
    const actions = el("div", { class: "tile-actions" });
    if (backend.active && backend.ready) {
      actions.append(el("a", { class: "linkbtn", href: backendUrl(backend), target: "_blank", rel: "noopener" }, t("tile.open")));
    }
    if (!backend.active) {
      const button = el("button", { type: "button", disabled: jobRunning }, t("tile.activate"));
      button.addEventListener("click", () => activate(button, backend, all, onChange));
      actions.append(button);
    }
    if (backend.key === "filaman" && backend.state !== "absent") {
      actions.append(el("button", { class: "quiet", type: "button", onclick: showFilamanLogin }, t("tile.login")));
    }
    if (backend.state !== "absent") {
      actions.append(el("button", { class: "quiet", type: "button", onclick: () => onLog(backend) }, t("tile.log")));
    }
    return el("div", { class: "tile" + (backend.active ? " active" : "") },
      el("div", { class: "tile-head" },
        el("img", { src: LOGOS[backend.key], alt: "" }),
        el("div", {}, el("div", { class: "tile-name", text: backend.label }),
          el("div", { class: "tile-port", text: ":" + backend.port }))),
      statePill(backend),
      el("p", { class: "hint", text: t("about." + backend.key) }),
      actions);
  }

  function backendsCard(data, jobRunning, onChange, onLog) {
    const stopAll = el("button", { class: "quiet", type: "button", disabled: jobRunning || !data.active }, t("backends.stop_all"));
    stopAll.addEventListener("click", async () => {
      if (!(await ask(t("backends.stop_all"), t("backends.stop_all_text"), t("backends.stop_all"), true))) return;
      await busy(stopAll, async () => { await api("/api/backends/stop", { method: "POST" }); onChange(); });
    });
    const card = el("section", { class: "card wide" },
      el("h2", {}, el("span", { text: t("backends.title") }), stopAll));
    if (!data.docker_ok) card.append(el("div", { class: "callout bd", text: t("err.docker_unavailable") }));
    card.append(el("div", { class: "tiles" }, data.backends.map((b) => tile(b, data.backends, jobRunning, onChange, onLog))));
    return card;
  }

  async function logCard(backend, onClose) {
    const body = el("div", { class: "log", text: t("common.loading") });
    const card = el("section", { class: "card wide" },
      el("h2", {}, el("span", { text: t("log.title", { name: backend.label }) }),
        el("button", { class: "quiet", type: "button", onclick: onClose }, t("common.close"))),
      body);
    try {
      const data = await api("/api/backends/" + backend.key + "/logs");
      body.textContent = data.lines.join("\n") || t("log.empty");
      body.scrollTop = body.scrollHeight;
    } catch (e) {
      toast(SSPro.errorText(e), true);
      body.textContent = "";
    }
    return card;
  }

  SSPro.views = Object.assign(SSPro.views || {}, { backendsCard, logCard });
})();
