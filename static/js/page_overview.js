/* SpoolmanScale Pro - the overview: backends, a running switch, the scale
 * and the Pi at a glance. This file owns the polling; the cards come from
 * view_backends.js and view_status.js.
 */
(function () {
  "use strict";
  const { el, api, toast, errorText, views } = SSPro;

  const POLL_MS = 5000;
  // Faster while a job runs, so each step shows as it happens.
  const POLL_JOB_MS = 1200;

  function render(main) {
    let timer = null;
    let stopped = false;
    let dismissedJob = null;

    const slots = {
      job: el("div", { class: "wrap" }),
      backends: el("div", { class: "wrap" }),
      log: el("div", { class: "wrap" }),
      cards: el("div", { class: "grid" }),
    };
    main.append(slots.job, slots.backends, slots.log, slots.cards);

    const refreshSoon = () => { clearTimeout(timer); timer = setTimeout(refresh, 0); };

    async function showLog(backend) {
      slots.log.replaceChildren(await views.logCard(backend, () => slots.log.replaceChildren()));
    }

    function drawJob(job, backends) {
      const show = job && (job.running || job.id !== dismissedJob);
      if (!show) { slots.job.replaceChildren(); return; }
      const target = backends.find((b) => b.key === job.target);
      slots.job.replaceChildren(views.jobCard(job, target ? target.label : job.target, () => {
        dismissedJob = job.id;
        slots.job.replaceChildren();
      }));
    }

    async function refresh() {
      if (stopped) return;
      let jobRunning = false;
      try {
        const [backends, job, scale, system] = await Promise.all([
          api("/api/backends"), api("/api/job"), api("/api/scale"), api("/api/system")]);
        jobRunning = !!(job.job && job.job.running);
        drawJob(job.job, backends.backends);
        slots.backends.replaceChildren(views.backendsCard(backends, jobRunning, refreshSoon, showLog));
        slots.cards.replaceChildren(views.scaleCard(scale.scale, refreshSoon), views.systemCard(system, refreshSoon));
      } catch (e) {
        if (e.code !== "login_required") toast(errorText(e), true);
      }
      if (!stopped) timer = setTimeout(refresh, jobRunning ? POLL_JOB_MS : POLL_MS);
    }

    refresh();
    return () => { stopped = true; clearTimeout(timer); };
  }

  SSPro.pages.overview = { nav: "nav.overview", render };
})();
