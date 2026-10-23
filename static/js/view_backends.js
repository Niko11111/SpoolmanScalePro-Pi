/* SpoolmanScale Pro - the backend tiles and the progress of a switch.
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
  const SWITCH_STEPS = ["stopping_others", "starting", "waiting_ready", "switching_scale"];

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

  function stepClass(index, current, job) {
    if (SWITCH_STEPS[index] === "switching_scale" && job.result.scale === "not_paired") return "skipped";
    if (job.ok) return "done";
    if (index < current) return "done";
    if (index === current) return job.running ? "now" : "failed";
    return "";
  }

  // label: the target's name as the tiles show it.
  function jobCard(job, label, onDismiss) {
    const current = SWITCH_STEPS.indexOf(job.step);
    const titleKey = "job.title_" + job.kind;
    const card = el("section", { class: "card wide" },
      el("h2", {}, el("span", { text: t(titleKey, { to: label }) }),
        job.running ? null : el("button", { class: "quiet", type: "button", onclick: onDismiss }, t("common.close"))));
    if (job.kind === "switch") {
      card.append(el("ol", { class: "steps" },
        SWITCH_STEPS.map((step, i) => {
          const cls = stepClass(i, current, job);
          return el("li", { class: cls }, t("step." + step), cls === "skipped" ? " - " + t("step.skipped_no_scale") : null);
        })));
    }
    if (job.ok === true) card.append(el("div", { class: "callout ok", text: t("job.done") }));
    if (job.ok === false) card.append(el("div", { class: "callout bd", text: t("err." + job.error) }));
    for (const code of job.warnings) card.append(el("div", { class: "callout wr", text: t("warn." + code) }));
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

  SSPro.views = Object.assign(SSPro.views || {}, { backendsCard, jobCard, logCard });
})();
