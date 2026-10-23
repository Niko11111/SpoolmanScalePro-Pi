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

  // On a small Pi (Zero 2 W) only Spoolman runs at a comfortable pace; the
  // others come with a warning (hardware.py, "slow_backends").
  function slowWarning(backend, plan) {
    return plan.rules.slow_backends.includes(backend.key) ? " " + t("switch.slow", { name: backend.label }) : "";
  }

  async function activate(button, backend, ctx) {
    const current = ctx.all.find((b) => b.active && b !== backend);
    const text = (current
      ? t("switch.confirm_text", { from: current.label, to: backend.label })
      : t("switch.confirm_first", { to: backend.label })) + slowWarning(backend, ctx.plan);
    if (!(await ask(t("switch.confirm_title", { to: backend.label }), text, t("switch.confirm_button")))) return;
    await busy(button, async () => {
      await api("/api/backends/" + backend.key + "/activate", { method: "POST" });
      ctx.onChange();
    });
  }

  // Next to the running ones. On a Pi 3 the server asks for a confirmation
  // with the numbers; the second request carries it.
  async function startBackend(button, backend, ctx) {
    await busy(button, async () => {
      try {
        await api("/api/backends/" + backend.key + "/start", { method: "POST", body: {} });
      } catch (e) {
        if (e.code !== "confirm_needed") throw e;
        const b = e.data.budget;
        const text = t("par.confirm_text", { after: b.after_mb, total: b.total_mb }) + (b.fits ? "" : " " + t("par.over"));
        if (!(await ask(t("par.confirm_title", { name: backend.label }), text, t("par.start")))) return;
        await api("/api/backends/" + backend.key + "/start", { method: "POST", body: { confirm: true } });
      }
      ctx.onChange();
    });
  }

  function post(label, path, ctx, cls) {
    const button = el("button", { type: "button", class: cls || "", disabled: ctx.jobRunning }, t(label));
    button.addEventListener("click", () => busy(button, async () => {
      await api(path, { method: "POST" });
      ctx.onChange();
    }));
    return button;
  }

  // One backend at a time: Open the active one, Activate the others. The
  // active one gets Activate too once it stopped (a switch away from it that
  // failed, a crash), or the only way back would be "Stop all".
  function singleActions(backend, ctx) {
    if (backend.active && backend.ready) {
      return [el("a", { class: "linkbtn", href: backendUrl(backend), target: "_blank", rel: "noopener" }, t("tile.open"))];
    }
    if (backend.active && backend.state === "running") return [];
    const button = el("button", { type: "button", disabled: ctx.jobRunning }, t("tile.activate"));
    button.addEventListener("click", () => activate(button, backend, ctx));
    return [button];
  }

  // Several at once: start and stop each, and choose the scale's.
  function parallelActions(backend, ctx) {
    const base = "/api/backends/" + backend.key;
    if (backend.state !== "running") {
      const button = el("button", { type: "button", disabled: ctx.jobRunning }, t("tile.start"));
      button.addEventListener("click", () => startBackend(button, backend, ctx));
      return [button];
    }
    const out = [];
    if (backend.ready) out.push(el("a", { class: "linkbtn", href: backendUrl(backend), target: "_blank", rel: "noopener" }, t("tile.open")));
    if (!backend.active) out.push(post("tile.use", base + "/use", ctx));
    out.push(post("tile.stop", base + "/stop", ctx, "quiet"));
    return out;
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

  function tile(backend, ctx) {
    const actions = el("div", { class: "tile-actions" },
      ctx.plan.parallel ? parallelActions(backend, ctx) : singleActions(backend, ctx));
    if (backend.key === "filaman" && backend.state !== "absent") {
      actions.append(el("button", { class: "quiet", type: "button", onclick: showFilamanLogin }, t("tile.login")));
    }
    if (backend.state !== "absent") {
      actions.append(el("button", { class: "quiet", type: "button", onclick: () => ctx.onLog(backend) }, t("tile.log")));
    }
    const badges = el("div", { class: "inrow" }, statePill(backend),
      ctx.plan.parallel && backend.active ? el("span", { class: "pill ok" }, t("tile.scale_uses")) : null,
      backend.ram_mb ? el("span", { class: "tile-port", text: t("tile.ram", { mb: backend.ram_mb }) }) : null);
    return el("div", { class: "tile" + (backend.active ? " active" : "") },
      el("div", { class: "tile-head" },
        el("img", { src: LOGOS[backend.key], alt: "" }),
        el("div", {}, el("div", { class: "tile-name", text: backend.label }),
          el("div", { class: "tile-port", text: ":" + backend.port }))),
      badges,
      el("p", { class: "hint", text: t("about." + backend.key) }),
      actions);
  }

  // With two or more running, the addresses they use to reach each other:
  // they share Docker's network, where a backend is its service name.
  function linksCard(data) {
    const running = data.backends.filter((b) => b.state === "running").map((b) => b.key);
    if (running.length < 2) return null;
    const rows = [];
    if (running.includes("bambuddy") && running.includes("spoolman")) rows.push(["par.bb_spoolman", "http://spoolman:8000"]);
    if (running.includes("filaman") && running.includes("bambuddy")) rows.push(["par.fm_bambuddy", "http://bambuddy:8000"]);
    if (!rows.length) return null;
    return el("section", { class: "card wide" }, el("h2", { text: t("par.links_title") }),
      el("div", { class: "rows" }, rows.map(([key, url]) =>
        el("div", { class: "row" }, el("span", { class: "k", text: t(key) }), el("span", { class: "v mono", text: url })))),
      el("p", { class: "note", text: t("par.links_note") }));
  }

  function backendsCard(data, jobRunning, onChange, onLog) {
    const ctx = { all: data.backends, jobRunning, onChange, onLog, plan: data.plan };
    const stopAll = el("button", { class: "quiet", type: "button", disabled: jobRunning || !data.backends.some((b) => b.state === "running") }, t("backends.stop_all"));
    stopAll.addEventListener("click", async () => {
      if (!(await ask(t("backends.stop_all"), t("backends.stop_all_text"), t("backends.stop_all"), true))) return;
      await busy(stopAll, async () => { await api("/api/backends/stop", { method: "POST" }); onChange(); });
    });
    const card = el("section", { class: "card wide" },
      el("h2", {}, el("span", { text: t("backends.title") }), stopAll));
    if (!data.docker_ok) card.append(el("div", { class: "callout bd", text: t("err.docker_unavailable") }));
    card.append(el("div", { class: "tiles" }, data.backends.map((b) => tile(b, ctx))));
    const links = linksCard(data);
    return links ? el("div", { class: "wrap" }, card, links) : card;
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
