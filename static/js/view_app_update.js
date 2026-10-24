/* SpoolmanScale Pro - updating SpoolmanScale Pro itself (app_update.py):
 * the installed version, newer releases with their notes, installing one,
 * and going back to the one installed before.
 *
 * Installing restarts the service. The card then asks for the version every
 * few seconds and reloads the page once the new one answers.
 */
(function () {
  "use strict";
  const { t, el, api, ask, busy, toast, errorText, views } = SSPro;

  const POLL_MS = 3000;
  // An update downloads, checks, reinstalls the Python packages and
  // restarts; past this, something went wrong and the log says what.
  const GIVE_UP_MS = 10 * 60 * 1000;

  function waitForNewVersion(slot, from) {
    const started = Date.now();
    const box = el("div", { class: "log", text: "" });
    slot.replaceChildren(el("div", { class: "callout wr", text: t("app.updating") }), box);
    async function poll() {
      try {
        const data = await api("/api/updates/app/state");
        box.textContent = data.state.lines.join("\n");
        if (data.version !== from) { location.reload(); return; }
        if (!data.state.running && data.state.exit !== null && data.state.exit !== 0) {
          slot.prepend(el("div", { class: "callout bd", text: t("app.failed") }));
          return;
        }
      } catch (e) {
        // The service restarts during the update: no answer is expected here.
      }
      if (Date.now() - started < GIVE_UP_MS) setTimeout(poll, POLL_MS);
      else slot.prepend(el("div", { class: "callout bd", text: t("app.timeout") }));
    }
    setTimeout(poll, POLL_MS);
  }

  function installRow(info, slot) {
    const choice = el("select", {}, info.newer.map((v) => el("option", { value: v }, v)));
    const install = el("button", { type: "button" }, t("upd.install"));
    install.addEventListener("click", async () => {
      if (!(await ask(t("app.install_title", { version: choice.value }), t("app.install_text"), t("upd.install")))) return;
      await busy(install, async () => {
        await api("/api/updates/app", { method: "POST", body: { version: choice.value } });
        waitForNewVersion(slot, info.current);
      });
    });
    return el("div", { class: "field" }, el("label", { text: t("upd.choose") }), el("div", { class: "inrow" }, choice, install));
  }

  function rollbackButton(info, slot) {
    const back = el("button", { type: "button", class: "quiet" }, t("app.rollback", { version: info.previous }));
    back.addEventListener("click", async () => {
      if (!(await ask(t("app.rollback", { version: info.previous }), t("app.rollback_text"), t("app.rollback_go"), true))) return;
      await busy(back, async () => {
        await api("/api/updates/app/rollback", { method: "POST" });
        waitForNewVersion(slot, info.current);
      });
    });
    return back;
  }

  function result(info, slot) {
    if (info.error) return [el("div", { class: "callout bd", text: errorText({ code: info.error }) })];
    if (!info.newer.length) return [el("div", { class: "callout ok", text: t("upd.up_to_date") })];
    const parts = [el("div", { class: "callout wr", text: t("upd.available", { version: info.newer[0] }) }), installRow(info, slot)];
    if (info.notes.length) {
      parts.push(el("p", { class: "note", text: t("upd.notes_title") }),
        ...info.notes.map((release, i) => views.releaseNotes(release, i === 0)));
    }
    return parts;
  }

  function row(key, value, mono) {
    return el("div", { class: "row" }, el("span", { class: "k", text: t(key) }),
      el("span", { class: mono ? "v mono" : "v", text: value }));
  }

  // kept: what the search on its own found last (update_watch.py), if it
  // still applies. Going back is offered after a search of its own.
  function appCard(kept) {
    const slot = el("div", { class: "wrap" });
    const search = el("button", { type: "button", class: "quiet" }, t("upd.search"));
    const current = document.documentElement.dataset.version;
    const rows = el("div", { class: "rows" });
    const tools = el("div", { class: "btnrow" });
    function show(info, at, error) {
      // replaceChildren() would write a null as the text "null".
      rows.replaceChildren(...[row("upd.installed", current, true), at ? row("upd.checked", SSPro.formatClock(at)) : null,
        error ? row("upd.last_try", errorText({ code: error })) : null].filter(Boolean));
      slot.replaceChildren(...result({ current, ...info }, slot));
    }
    if (kept) show(kept.result, kept.at, kept.error);
    else rows.replaceChildren(row("upd.installed", current, true));
    async function run() {
      const info = (await api("/api/updates/app")).app;
      show(info, info.error ? null : info.at);
      tools.replaceChildren(...(info.previous ? [rollbackButton(info, slot)] : []));
    }
    search.addEventListener("click", () => busy(search, run));
    const card = el("section", { class: "card wide" }, el("h2", {}, el("span", { text: "SpoolmanScale Pro" }), search),
      rows, slot, tools, el("p", { class: "note", text: t("app.note") }));
    card.search = run;
    return card;
  }

  SSPro.views = Object.assign(SSPro.views || {}, { appCard });
})();
