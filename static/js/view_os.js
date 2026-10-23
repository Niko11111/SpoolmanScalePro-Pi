/* SpoolmanScale Pro - the Raspberry Pi OS update on the System page:
 * search (lists every package, installs nothing), install (with apt's log
 * live), and the restart a new kernel needs.
 *
 * The card follows its jobs itself; the search result arrives as the
 * os_check job's result, the log as the os_upgrade job's lines.
 */
(function () {
  "use strict";
  const { t, el, api, ask, busy, toast, errorText, views } = SSPro;

  function packageList(result) {
    const rows = result.packages.map((p) => el("div", { class: "row" },
      el("span", { class: "k mono", text: p.name }),
      el("span", { class: "v mono", text: (p.current || t("os.new")) + " → " + p.candidate })));
    return el("div", { class: "scrollbox" }, el("div", { class: "rows" }, rows));
  }

  function restartButton() {
    const button = el("button", { type: "button" }, t("os.restart_now"));
    button.addEventListener("click", async () => {
      if (!(await ask(t("power.reboot"), t("power.reboot_text"), t("power.reboot")))) return;
      await busy(button, async () => {
        await api("/api/system/reboot", { method: "POST" });
        toast(t("power.reboot_started"));
      });
    });
    return button;
  }

  function searchResult(result, startUpgrade) {
    const count = result.summary ? result.summary.upgraded + result.summary.newly_installed : result.packages.length;
    if (!count) return [el("div", { class: "callout ok", text: t("os.up_to_date") })];
    const parts = [el("div", { class: "callout wr", text: t("os.found", { n: count }) }), packageList(result)];
    if (result.mismatch) parts.push(el("p", { class: "hint", text: t("os.mismatch", { n: count }) }));
    if (result.removals.length) parts.push(el("div", { class: "callout wr", text: t("os.removals", { names: result.removals.join(", ") }) }));
    if (result.restart_after) parts.push(el("p", { class: "hint", text: t("os.kernel") }));
    const install = el("button", { type: "button" }, t("os.install"));
    install.addEventListener("click", async () => {
      if (!(await ask(t("os.install_title"), t("os.install_text", { n: count }), t("os.install")))) return;
      startUpgrade(install);
    });
    parts.push(el("div", { class: "btnrow" }, install));
    return parts;
  }

  function osCard() {
    const jobSlot = el("div", { class: "wrap" });
    const resultSlot = el("div", { class: "wrap" });
    const search = el("button", { type: "button", class: "quiet" }, t("os.search"));
    let unfollow = null;

    function onEnd(job) {
      if (job.kind === "os_check" && job.ok) resultSlot.replaceChildren(...searchResult(job.result, startUpgrade));
      if (job.kind === "os_upgrade" && job.ok && job.result.restart_needed) {
        resultSlot.replaceChildren(el("div", { class: "callout wr", text: t("os.restart_needed") }), restartButton());
      }
    }
    function follow() {
      if (unfollow) unfollow();
      unfollow = views.followJob(jobSlot, () => t("os.the_pi"), onEnd, false);
    }
    function start(button, path) {
      return busy(button, async () => {
        resultSlot.replaceChildren();
        await api(path, { method: "POST" });
        follow();
      });
    }
    function startUpgrade(button) { return start(button, "/api/system/os/upgrade"); }

    search.addEventListener("click", () => start(search, "/api/system/os/check"));
    const card = el("section", { class: "card wide" }, el("h2", {}, el("span", { text: t("os.title") }), search),
      el("p", { class: "hint", text: t("os.hint") }), jobSlot, resultSlot);

    // An upgrade that runs already (page reloaded, service restarted) is
    // picked up; a restart still owed from an earlier one is offered.
    api("/api/system/os").then(async (state) => {
      if (state.upgrade_running) {
        try { await api("/api/system/os/follow", { method: "POST" }); } catch (e) { /* the job runner follows it already */ }
        follow();
      } else if (state.restart_needed) {
        resultSlot.replaceChildren(el("div", { class: "callout wr", text: t("os.restart_needed") }), restartButton());
      }
    }).catch((e) => { if (e.code !== "login_required") toast(errorText(e), true); });
    card.stop = () => { if (unfollow) unfollow(); };
    return card;
  }

  SSPro.views = Object.assign(SSPro.views || {}, { osCard });
})();
