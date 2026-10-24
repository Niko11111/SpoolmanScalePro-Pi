/* SpoolmanScale Pro - a backend's daily build on the Updates page
 * (backend_daily.py): offering the switch, a newer build, and the two ways
 * back to the releases. Each one is a job the page follows like an update.
 */
(function () {
  "use strict";
  const { t, el, ask, views } = SSPro;

  // "2026-10-24_120000" in a backup's name.
  const BACKUP_DAY_RE = /_(\d{4}-\d{2}-\d{2})_\d{6}/;

  function day(isoDate) {
    return new Date(isoDate).toLocaleDateString(SSPro.lang, { dateStyle: "medium" });
  }

  // release: the build's GitHub pre-release ({tag, published}), or null.
  function buildName(release) {
    return release ? t("daily.build", { date: day(release.published), version: release.tag }) : "";
  }

  function actionButton(label, danger, confirm, run) {
    const button = el("button", { type: "button", class: danger ? "danger" : "" }, label);
    button.addEventListener("click", async () => {
      if (await ask(confirm.title, confirm.text, label, danger)) run(button);
    });
    return button;
  }

  function installButton(backend, label, title, text, start) {
    return actionButton(label, false, { title, text },
      (button) => start(button, "/api/updates/" + backend.key + "/daily", {}));
  }

  // Not on the daily build yet: what it is, and the switch.
  function dailyOffer(backend, daily, start) {
    const newest = daily.newest ? el("p", { class: "hint", text: t("daily.newest_is", { build: buildName(daily.newest) }) }) : null;
    return el("div", { class: "wrap" }, el("p", { class: "note", text: t("daily.title") }),
      el("p", { class: "hint", text: t("daily.about", { name: backend.label }) }), newest,
      el("div", { class: "btnrow" }, installButton(backend, t("daily.switch"), t("daily.switch_title", { name: backend.label }),
        t("daily.switch_text", { name: backend.label }), start)));
  }

  // On the daily build: going back now, with the backup from before.
  function leaveNow(backend, back, start) {
    if (!back) return el("p", { class: "hint", text: t("daily.no_backup") });
    const match = back.backup.match(BACKUP_DAY_RE);
    const since = match ? day(match[1]) : back.backup;
    const label = t("daily.leave", { version: back.version });
    return el("div", { class: "wrap" }, el("p", { class: "hint", text: t("daily.leave_hint", { date: since }) }),
      el("div", { class: "btnrow" }, actionButton(label, true,
        { title: label, text: t("daily.leave_text", { name: backend.label, date: since, version: back.version }) },
        (button) => start(button, "/api/updates/" + backend.key + "/leave-daily", {}))));
  }

  // releases: the parts that offer a release newer than the daily build
  // (page_updates.js), empty while there is none.
  function dailyOn(backend, update, start, releases) {
    const daily = update.daily;
    const parts = [];
    if (daily.installed) parts.push(el("p", { class: "hint", text: t("daily.running", { build: buildName(daily.installed) }) }));
    if (daily.update) {
      parts.push(el("div", { class: "callout wr", text: daily.newest ? t("daily.newer", { build: buildName(daily.newest) }) : t("daily.newer_plain") }),
        el("div", { class: "btnrow" }, installButton(backend, t("upd.install"), t("daily.update_title", { name: backend.label }),
          t("upd.install_text_running", { name: backend.label }), start)));
      if (daily.newest && daily.newest.body) parts.push(views.releaseNotes(daily.newest, false));
    } else {
      parts.push(el("div", { class: "callout ok", text: t("daily.up_to_date") }));
    }
    parts.push(el("p", { class: "note", text: t("daily.back_title") }));
    if (releases.length) parts.push(...releases);
    else parts.push(el("p", { class: "hint", text: t("daily.no_release_yet") }));
    parts.push(leaveNow(backend, daily.back, start));
    return parts;
  }

  SSPro.views = Object.assign(SSPro.views || {}, { dailyOffer, dailyOn });
})();
