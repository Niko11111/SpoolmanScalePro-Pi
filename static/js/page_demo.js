/* SpoolmanScale Pro - the demo page: reset everything to the demo state
 * with one button, and save a backend's current state as its demo state.
 * Only in the navigation while demo mode is enabled on this Pi.
 */
(function () {
  "use strict";
  const { t, el, api, ask, busy, toast, errorText, views } = SSPro;

  function resetCard(snapshots, start) {
    const saved = snapshots.filter((s) => s.saved);
    const button = el("button", { type: "button", class: "big", disabled: !saved.length }, t("demo.reset"));
    button.addEventListener("click", async () => {
      if (!(await ask(t("demo.reset"), t("demo.reset_text"), t("demo.reset"), true))) return;
      start(button, "/api/demo/reset");
    });
    return el("section", { class: "card wide" }, el("h2", { text: t("demo.reset_title") }),
      el("p", { class: "hint", text: saved.length ? t("demo.reset_hint", { names: saved.map((s) => s.label).join(", ") }) : t("demo.nothing_saved") }),
      button);
  }

  function saveRow(snapshot, start) {
    const button = el("button", { type: "button", class: "quiet" }, t("demo.save"));
    button.addEventListener("click", async () => {
      const text = t(snapshot.saved ? "demo.save_text_replace" : "demo.save_text", { name: snapshot.label });
      if (!(await ask(t("demo.save_title", { name: snapshot.label }), text, t("demo.save")))) return;
      start(button, "/api/demo/" + snapshot.key + "/save");
    });
    const state = snapshot.saved
      ? el("span", { class: "pill ok" }, new Date(snapshot.saved).toLocaleString(SSPro.lang, { dateStyle: "short", timeStyle: "short" }))
      : el("span", { class: "pill off" }, t("demo.not_saved"));
    return el("div", { class: "row center" },
      el("div", { class: "stack" }, el("span", { class: "k", text: snapshot.label }), state), button);
  }

  function saveCard(snapshots, start) {
    return el("section", { class: "card wide" }, el("h2", { text: t("demo.states_title") }),
      el("div", { class: "rows" }, snapshots.map((s) => saveRow(s, start))),
      el("p", { class: "note", text: t("demo.states_note") }));
  }

  function render(main) {
    const jobSlot = el("div", { class: "wrap" });
    const cards = el("div", { class: "wrap" });
    main.append(jobSlot, cards);
    let unfollow = null;
    let labelOf = (key) => key;

    async function draw() {
      try {
        const [demo, backends] = await Promise.all([api("/api/demo"), api("/api/backends")]);
        labelOf = views.labelsFrom(backends.backends);
        cards.replaceChildren(resetCard(demo.snapshots, start), saveCard(demo.snapshots, start));
      } catch (e) {
        if (e.code !== "login_required") toast(errorText(e), true);
      }
    }

    function follow(onlyIfRunning) {
      if (unfollow) unfollow();
      unfollow = views.followJob(jobSlot, (key) => labelOf(key), draw, onlyIfRunning);
    }

    function start(button, path) {
      return busy(button, async () => {
        await api(path, { method: "POST" });
        follow(false);
      });
    }

    draw().then(() => follow(true));
    return () => { if (unfollow) unfollow(); };
  }

  SSPro.pages.demo = { nav: "nav.demo", render, visible: (system) => system.demo_enabled };
})();
