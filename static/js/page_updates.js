/* SpoolmanScale Pro - updates of the backends: what runs, what is newer,
 * what changed (release notes from GitHub), and installing a version.
 * Searching asks ghcr.io and GitHub, so it only happens on a click.
 */
(function () {
  "use strict";
  const { t, el, api, ask, busy, toast, errorText, views } = SSPro;

  function versionRows(update) {
    const rows = [el("div", { class: "row" }, el("span", { class: "k", text: t("upd.installed") }),
      el("span", { class: "v mono", text: update.current }))];
    if (update.current !== update.default) {
      rows.push(el("div", { class: "row" }, el("span", { class: "k", text: t("upd.tested") }),
        el("span", { class: "v mono", text: update.default })));
    }
    return el("div", { class: "rows" }, rows);
  }

  function installForm(backend, update, start) {
    const choice = el("select", {}, update.newer.map((tag) => el("option", { value: tag }, tag)));
    const install = el("button", { type: "button" }, t("upd.install"));
    install.addEventListener("click", async () => {
      const text = t(backend.state === "running" ? "upd.install_text_running" : "upd.install_text", { name: backend.label });
      if (!(await ask(t("upd.install_title", { name: backend.label, version: choice.value }), text, t("upd.install")))) return;
      start(install, "/api/updates/" + backend.key, { version: choice.value });
    });
    return el("div", { class: "field" }, el("label", { text: t("upd.choose") }), el("div", { class: "inrow" }, choice, install));
  }

  function result(backend, update, start) {
    if (!update.newer.length) return [el("div", { class: "callout ok", text: t("upd.up_to_date") })];
    const parts = [el("div", { class: "callout wr", text: t("upd.available", { version: update.newer[0] }) }),
      installForm(backend, update, start)];
    if (update.notes.length) {
      parts.push(el("p", { class: "note", text: t("upd.notes_title") }),
        ...update.notes.map((release, i) => views.releaseNotes(release, i === 0)));
    }
    return parts;
  }

  function backendCard(backend, start) {
    const slot = el("div", { class: "wrap" });
    const search = el("button", { type: "button", class: "quiet" }, t("upd.search"));
    const card = el("section", { class: "card wide" }, el("h2", {}, el("span", { text: backend.label }), search), slot);
    async function run() {
      try {
        const update = (await api("/api/updates/" + backend.key)).update;
        slot.replaceChildren(versionRows(update), ...result(backend, update, start));
      } catch (e) {
        slot.replaceChildren(el("div", { class: "callout bd", text: errorText(e) }));
      }
    }
    search.addEventListener("click", () => busy(search, run));
    card.search = run;
    return card;
  }

  function optionsCard(settings, cards) {
    const box = el("input", { type: "checkbox", checked: settings.include_prereleases });
    box.addEventListener("change", async () => {
      try {
        await api("/api/settings", { method: "POST", body: { include_prereleases: box.checked } });
      } catch (e) {
        box.checked = !box.checked;
        toast(errorText(e), true);
      }
    });
    const all = el("button", { type: "button" }, t("upd.search_all"));
    all.addEventListener("click", () => busy(all, () => Promise.all(cards.map((c) => c.search()))));
    return el("section", { class: "card wide" }, el("h2", { text: t("upd.title") }),
      el("label", { class: "check" }, el("span", { text: t("upd.prereleases") }), el("span", { class: "switch" }, box, el("i", {}))),
      el("p", { class: "hint", text: t("upd.prereleases_hint") }),
      el("div", { class: "btnrow" }, all), el("p", { class: "note", text: t("upd.note") }));
  }

  function render(main) {
    const jobSlot = el("div", { class: "wrap" });
    const body = el("div", { class: "wrap" });
    main.append(jobSlot, body);
    let unfollow = null;
    let labelOf = (key) => key;

    function follow(onlyIfRunning) {
      if (unfollow) unfollow();
      unfollow = views.followJob(jobSlot, (key) => labelOf(key), draw, onlyIfRunning);
    }

    function start(button, path, payload) {
      return busy(button, async () => {
        await api(path, { method: "POST", body: payload });
        follow(false);
      });
    }

    async function draw() {
      try {
        const [backends, settings] = await Promise.all([api("/api/backends"), api("/api/settings")]);
        labelOf = views.labelsFrom(backends.backends);
        const cards = backends.backends.map((b) => backendCard(b, start));
        body.replaceChildren(optionsCard(settings.settings, cards), ...cards);
      } catch (e) {
        if (e.code !== "login_required") toast(errorText(e), true);
      }
    }

    draw().then(() => follow(true));
    return () => { if (unfollow) unfollow(); };
  }

  SSPro.pages.updates = { nav: "nav.updates", render };
})();
