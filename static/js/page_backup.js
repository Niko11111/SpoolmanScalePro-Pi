/* SpoolmanScale Pro - backups: make one per backend, keep the list,
 * download, restore, delete, and bring one back from a file.
 */
(function () {
  "use strict";
  const { t, el, api, ask, busy, toast, errorText, views } = SSPro;

  const BYTES_PER_KIB = 1024;

  function size(bytes) {
    const kib = bytes / BYTES_PER_KIB;
    return kib < BYTES_PER_KIB ? Math.round(kib) + " KiB" : (kib / BYTES_PER_KIB).toFixed(1) + " MiB";
  }

  function when(iso) {
    return new Date(iso).toLocaleString(SSPro.lang, { dateStyle: "medium", timeStyle: "short" });
  }

  function createCard(backends, start) {
    const rows = backends.map((b) => {
      const button = el("button", { type: "button", disabled: b.state === "absent" }, t("backup.make"));
      button.addEventListener("click", () => start(button, "/api/backups/" + b.key));
      return el("div", { class: "row" }, el("span", { class: "k", text: b.label }), button);
    });
    return el("section", { class: "card" }, el("h2", { text: t("backup.create_title") }),
      el("div", { class: "rows" }, rows), el("p", { class: "note", text: t("backup.create_note") }));
  }

  function uploadCard(backends, start) {
    const backend = el("select", {}, backends.map((b) => el("option", { value: b.key }, b.label)));
    const file = el("input", { type: "file", accept: ".tar" });
    const button = el("button", { type: "button", class: "danger" }, t("backup.upload_restore"));
    button.addEventListener("click", async () => {
      if (!file.files.length) { toast(t("err.no_file"), true); return; }
      const label = backend.selectedOptions[0].textContent;
      if (!(await ask(t("backup.restore_title", { name: label }), t("backup.restore_text"), t("backup.restore"), true))) return;
      const form = new FormData();
      form.append("file", file.files[0]);
      start(button, "/api/backups/upload/" + backend.value, form);
    });
    return el("section", { class: "card" }, el("h2", { text: t("backup.upload_title") }),
      el("div", { class: "field" }, el("label", { text: t("backup.upload_backend") }), backend),
      el("div", { class: "field" }, el("label", { text: t("backup.upload_file") }), file),
      el("div", { class: "btnrow" }, button), el("p", { class: "note", text: t("backup.upload_note") }));
  }

  function backupRow(item, labelOf, start, redraw) {
    const restore = el("button", { type: "button", class: "quiet" }, t("backup.restore"));
    restore.addEventListener("click", async () => {
      if (!(await ask(t("backup.restore_title", { name: labelOf(item.backend) }), t("backup.restore_text"), t("backup.restore"), true))) return;
      start(restore, "/api/backups/file/" + encodeURIComponent(item.name) + "/restore");
    });
    const remove = el("button", { type: "button", class: "quiet" }, t("backup.delete"));
    remove.addEventListener("click", async () => {
      if (!(await ask(t("backup.delete"), t("backup.delete_text", { name: item.name }), t("backup.delete"), true))) return;
      await busy(remove, async () => { await api("/api/backups/file/" + encodeURIComponent(item.name), { method: "DELETE" }); redraw(); });
    });
    return el("div", { class: "listrow" },
      el("div", {},
        el("div", { class: "nm" }, labelOf(item.backend), item.reason ? el("span", { class: "pill off" }, t("backup.reason_" + item.reason.replace("-", "_"))) : null),
        el("div", { class: "sz", text: when(item.created) + " - " + size(item.size) })),
      el("div", { class: "inrow" },
        el("a", { class: "linkbtn", href: "/api/backups/file/" + encodeURIComponent(item.name), download: item.name }, t("backup.download")),
        restore, remove));
  }

  function listCard(items, labelOf, start, redraw) {
    const card = el("section", { class: "card wide" }, el("h2", { text: t("backup.list_title") }));
    if (!items.length) card.append(el("p", { class: "hint", text: t("backup.none") }));
    for (const item of items) card.append(backupRow(item, labelOf, start, redraw));
    card.append(el("p", { class: "note", text: t("backup.list_note") }));
    return card;
  }

  function render(main) {
    const jobSlot = el("div", { class: "wrap" });
    const grid = el("div", { class: "grid" });
    main.append(jobSlot, grid);
    let unfollow = null;
    let labelOf = (key) => key;

    async function draw() {
      try {
        const [backends, list] = await Promise.all([api("/api/backends"), api("/api/backups")]);
        labelOf = views.labelsFrom(backends.backends);
        grid.replaceChildren(createCard(backends.backends, start), uploadCard(backends.backends, start),
          listCard(list.backups, labelOf, start, draw));
      } catch (e) {
        if (e.code !== "login_required") toast(errorText(e), true);
      }
    }

    function follow(onlyIfRunning) {
      if (unfollow) unfollow();
      unfollow = views.followJob(jobSlot, (key) => labelOf(key), draw, onlyIfRunning);
    }

    function start(button, path, body) {
      return busy(button, async () => {
        await api(path, { method: "POST", body: body });
        follow(false);
      });
    }

    draw().then(() => follow(true));
    return () => { if (unfollow) unfollow(); };
  }

  SSPro.pages.backup = { nav: "nav.backup", render };
})();
