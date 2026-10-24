/* SpoolmanScale Pro - the setup assistant: pick a backend, pair the scale,
 * done. Opens after the first login until it is finished or skipped
 * (setting "setup_done"); System opens it again.
 *
 * It holds no logic of its own: the backend tiles come from
 * view_backends.js, the pairing cards from page_scale.js.
 */
(function () {
  "use strict";
  const { t, el, api, toast, errorText, views } = SSPro;

  const STEPS = ["setup.step_backend", "setup.step_scale", "setup.step_done"];

  function progressBar(current) {
    return el("ol", { class: "wizard" }, STEPS.map((key, i) =>
      el("li", { class: i < current ? "done" : i === current ? "now" : "" }, t(key))));
  }

  async function finish() {
    try {
      await api("/api/settings", { method: "POST", body: { setup_done: true } });
    } catch (e) {
      toast(errorText(e), true);
      return;
    }
    location.hash = "#overview";
  }

  function navRow(back, next, nextLabel, nextEnabled) {
    return el("div", { class: "btnrow wizard-nav" },
      back ? el("button", { type: "button", class: "quiet", onclick: back }, t("setup.back")) : null,
      el("span", { class: "spacer" }),
      el("button", { type: "button", class: "quiet", onclick: finish }, t("setup.skip")),
      el("button", { type: "button", disabled: !nextEnabled, onclick: next }, nextLabel));
  }

  function render(main) {
    let step = 0;
    let timer = null;
    let unfollow = null;
    const body = el("div", { class: "wrap" });
    // One slot for the progress of a switch, kept across redraws: the job
    // view writes into this very node.
    const jobSlot = el("div", { class: "wrap" });
    main.append(el("section", { class: "card wide" }, el("h2", { text: t("setup.title_assistant") }),
      el("p", { class: "hint", text: t("setup.intro") })), body);

    function stop() { clearTimeout(timer); if (unfollow) unfollow(); unfollow = null; }
    function go(next) { stop(); jobSlot.replaceChildren(); step = next; draw(); }

    async function drawBackends() {
      const [data, jobData] = await Promise.all([api("/api/backends"), api("/api/job")]);
      const running = !!(jobData.job && jobData.job.running);
      const ready = data.backends.some((b) => b.active && b.ready);
      body.replaceChildren(progressBar(0), el("p", { class: "hint", text: t("setup.backend_hint") }),
        views.backendsCard(data, running, () => draw(), () => {}), jobSlot,
        navRow(null, () => go(1), t("setup.next"), ready && !running));
      if (running && !unfollow) {
        unfollow = views.followJob(jobSlot, views.labelsFrom(data.backends), () => { unfollow = null; draw(); }, false);
      }
      clearTimeout(timer);
      timer = setTimeout(draw, running ? 1500 : 5000);
    }

    async function drawScale() {
      const [settings, system, backends] = await Promise.all([api("/api/settings"), api("/api/system"), api("/api/backends")]);
      const piName = system.hostname.replace(/\.local$/, "") + ".local";
      body.replaceChildren(progressBar(1), el("p", { class: "hint", text: t("setup.scale_hint") }),
        el("div", { class: "grid" }, views.pairingCard(settings.settings, () => draw()),
          views.setupCard(piName, views.labelsFrom(backends.backends), !!settings.settings.scale_address,
            backends.active === "filaman")),
        navRow(() => go(0), () => go(2), t("setup.next"), true));
    }

    async function drawDone() {
      const [backends, scale] = await Promise.all([api("/api/backends"), api("/api/scale")]);
      const active = backends.backends.find((b) => b.active);
      body.replaceChildren(progressBar(2), el("section", { class: "card wide" },
        el("div", { class: "rows" },
          el("div", { class: "row" }, el("span", { class: "k", text: t("setup.summary_backend") }),
            el("span", { class: "v", text: active ? active.label : t("setup.none_backend") })),
          el("div", { class: "row" }, el("span", { class: "k", text: t("setup.summary_scale") }),
            el("span", { class: "v", text: scale.scale.paired ? scale.scale.address : t("setup.none_scale") }))),
        el("p", { class: "note", text: t("setup.done_note") })),
        el("div", { class: "btnrow wizard-nav" }, el("button", { type: "button", class: "quiet", onclick: () => go(1) }, t("setup.back")),
          el("span", { class: "spacer" }), el("button", { type: "button", onclick: finish }, t("setup.finish"))));
    }

    function draw() {
      const steps = [drawBackends, drawScale, drawDone];
      steps[step]().catch((e) => { if (e.code !== "login_required") toast(errorText(e), true); });
    }

    draw();
    return stop;
  }

  SSPro.pages.setup = { nav: "nav.setup", render, hidden: true };
})();
