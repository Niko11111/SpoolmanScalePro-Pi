/* SpoolmanScale Pro - updates of the backends: what runs, what is newer,
 * what changed (release notes from GitHub), and installing a version.
 * The page opens with what the search on its own found last
 * (update_watch.py); a click searches again. A backend's daily build is
 * drawn by view_daily.js.
 */
(function () {
  "use strict";
  const { t, el, api, ask, busy, toast, errorText, views } = SSPro;

  function row(key, value, mono) {
    return el("div", { class: "row" }, el("span", { class: "k", text: t(key) }),
      el("span", { class: mono ? "v mono" : "v", text: value }));
  }

  // at: when it was found (epoch seconds); error: the last search's
  // failure since, if any.
  function versionRows(update, at, error) {
    const rows = [row("upd.installed", update.shown || update.current, true)];
    if (update.current !== update.default) rows.push(row("upd.tested", update.default, true));
    if (at) rows.push(row("upd.checked", SSPro.formatClock(at)));
    if (error) rows.push(row("upd.last_try", errorText({ code: error })));
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
    const daily = update.daily;
    if (daily && daily.on) return views.dailyOn(backend, update, start, update.newer.length ? releases(backend, update, start) : []);
    const parts = releases(backend, update, start);
    if (daily) parts.push(views.dailyOffer(backend, daily, start));
    return parts;
  }

  function releases(backend, update, start) {
    if (!update.newer.length) return [el("div", { class: "callout ok", text: t("upd.up_to_date") })];
    const parts = [el("div", { class: "callout wr", text: t("upd.available", { version: update.newer[0] }) }),
      installForm(backend, update, start)];
    if (update.notes.length) {
      parts.push(el("p", { class: "note", text: t("upd.notes_title") }),
        ...update.notes.map((release, i) => views.releaseNotes(release, i === 0)));
    }
    return parts;
  }

  // kept: what the search found last for this backend, if it still applies.
  function backendCard(backend, start, kept) {
    const slot = el("div", { class: "wrap" });
    const search = el("button", { type: "button", class: "quiet" }, t("upd.search"));
    const card = el("section", { class: "card wide" }, el("h2", {}, el("span", { text: backend.label }), search), slot);
    const show = (update, at, error) => slot.replaceChildren(versionRows(update, at, error), ...result(backend, update, start));
    async function run() {
      try {
        const found = await api("/api/updates/" + backend.key);
        show(found.update, found.at);
      } catch (e) {
        slot.replaceChildren(el("div", { class: "callout bd", text: errorText(e) }));
      }
    }
    if (kept) show(kept.result, kept.at, kept.error);
    search.addEventListener("click", () => busy(search, run));
    card.search = run;
    return card;
  }

  // A switch for one boolean setting, stored as it is flipped.
  function settingSwitch(settings, name, label) {
    const box = el("input", { type: "checkbox", checked: settings[name] });
    box.addEventListener("change", async () => {
      try {
        await api("/api/settings", { method: "POST", body: { [name]: box.checked } });
      } catch (e) {
        box.checked = !box.checked;
        toast(errorText(e), true);
      }
    });
    return el("label", { class: "check" }, el("span", { text: t(label) }), el("span", { class: "switch" }, box, el("i", {})));
  }

  function optionsCard(settings, cards) {
    const all = el("button", { type: "button" }, t("upd.search_all"));
    all.addEventListener("click", () => busy(all, () => Promise.all(cards.map((c) => c.search()))));
    return el("section", { class: "card wide" }, el("h2", { text: t("upd.title") }),
      settingSwitch(settings, "update_check", "upd.auto"),
      el("p", { class: "hint", text: t("upd.auto_hint") }),
      settingSwitch(settings, "include_prereleases", "upd.prereleases"),
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
        const [backends, settings, known] = await Promise.all([api("/api/backends"), api("/api/settings"), api("/api/updates/known")]);
        labelOf = views.labelsFrom(backends.backends);
        const cards = backends.backends.map((b) => backendCard(b, start, known.items[b.key]));
        const app = views.appCard(known.items.app);
        body.replaceChildren(app, optionsCard(settings.settings, [app, ...cards]), ...cards);
      } catch (e) {
        if (e.code !== "login_required") toast(errorText(e), true);
      }
    }

    draw().then(() => follow(true));
    return () => { if (unfollow) unfollow(); };
  }

  SSPro.pages.updates = { nav: "nav.updates", render };
})();
