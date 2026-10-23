/* SpoolmanScale Pro - the progress of a job (switch, backup, restore,
 * demo save and reset), drawn from what /api/job returns.
 *
 * jobCard() draws one state. follow() keeps a slot up to date until the
 * job ends; pages that start a job use it, the overview has its own
 * polling and only uses jobCard().
 */
(function () {
  "use strict";
  const { t, el, api, errorText, toast } = SSPro;

  const SWITCH_STEPS = ["stopping_others", "starting", "waiting_ready", "switching_scale"];
  const POLL_MS = 1200;

  function switchStepClass(index, job) {
    const current = SWITCH_STEPS.indexOf(job.step);
    if (SWITCH_STEPS[index] === "switching_scale" && job.result.scale === "not_paired") return "skipped";
    if (job.ok) return "done";
    if (index < current) return "done";
    if (index === current) return job.running ? "now" : "failed";
    return "";
  }

  function switchSteps(job) {
    return el("ol", { class: "steps" }, SWITCH_STEPS.map((step, i) => {
      const cls = switchStepClass(i, job);
      return el("li", { class: cls }, t("step." + step), cls === "skipped" ? " - " + t("step.skipped_no_scale") : null);
    }));
  }

  // Every other kind reports one step at a time; shown while it runs.
  function currentStep(job, labelOf) {
    if (!job.running) return null;
    const on = job.result.current ? " (" + labelOf(job.result.current) + ")" : "";
    return el("ol", { class: "steps" }, el("li", { class: "now" }, t("step." + job.step) + on));
  }

  // labelOf: backend key -> the name the tiles show.
  function jobCard(job, labelOf, onDismiss) {
    const card = el("section", { class: "card wide" },
      el("h2", {}, el("span", { text: t("job.title_" + job.kind, { to: labelOf(job.target) }) }),
        job.running ? null : el("button", { class: "quiet", type: "button", onclick: onDismiss }, t("common.close"))));
    const steps = job.kind === "switch" ? switchSteps(job) : currentStep(job, labelOf);
    if (steps) card.append(steps);
    if (job.ok === true) card.append(el("div", { class: "callout ok", text: t("job.done") }));
    if (job.ok === false) card.append(el("div", { class: "callout bd", text: t("err." + job.error) }));
    for (const code of job.warnings) card.append(el("div", { class: "callout wr", text: t("warn." + code) }));
    if (job.lines && job.lines.length) {
      const box = el("div", { class: "log", text: job.lines.join("\n") });
      card.append(box);
      // After the card is in the page: the newest line in view.
      requestAnimationFrame(() => { box.scrollTop = box.scrollHeight; });
    }
    return card;
  }

  // Draws the current job into slot until it has ended, then calls onEnd
  // once. onlyIfRunning: on opening a page, a job that already ended
  // (possibly long ago, on another page) is not shown. Returns a function
  // that stops following.
  function follow(slot, labelOf, onEnd, onlyIfRunning) {
    let timer = null;
    let stopped = false;
    let first = true;
    async function tick() {
      if (stopped) return;
      try {
        const job = (await api("/api/job")).job;
        const skip = !job || (first && onlyIfRunning && !job.running);
        first = false;
        if (skip) { slot.replaceChildren(); return; }
        slot.replaceChildren(jobCard(job, labelOf, () => slot.replaceChildren()));
        if (job.running) { timer = setTimeout(tick, POLL_MS); return; }
        if (onEnd) onEnd(job);
      } catch (e) {
        if (e.code !== "login_required") toast(errorText(e), true);
      }
    }
    tick();
    return () => { stopped = true; clearTimeout(timer); };
  }

  function labelsFrom(backends) {
    const names = Object.fromEntries(backends.map((b) => [b.key, b.label]));
    return (key) => names[key] || t("job.all_backends");
  }

  SSPro.views = Object.assign(SSPro.views || {}, { jobCard, followJob: follow, labelsFrom });
})();
