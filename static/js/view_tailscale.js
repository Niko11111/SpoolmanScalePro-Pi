/* SpoolmanScale Pro - remote access with Tailscale on the System page
 * (tailscale.py): install, connect with the login link Tailscale gives,
 * disconnect. While it installs or waits for the login, the card asks every
 * few seconds and shows the log.
 */
(function () {
  "use strict";
  const { t, el, api, ask, busy, toast, errorText } = SSPro;

  const POLL_MS = 2000;
  const WAITING = ["NeedsLogin", "Starting", "NoState"];

  function row(label, value) {
    return el("div", { class: "row" }, el("span", { class: "k", text: label }), el("span", { class: "v mono", text: value }));
  }

  function tailscaleCard() {
    const body = el("div", { class: "wrap" });
    const card = el("section", { class: "card" }, el("h2", { text: t("ts.title") }),
      el("p", { class: "hint", text: t("ts.hint") }), body);
    let timer = null;

    const action = (label, path, confirmKey, kind) => {
      const button = el("button", { type: "button", class: kind || "" }, t(label));
      button.addEventListener("click", async () => {
        if (confirmKey && !(await ask(t(label), t(confirmKey), t(label)))) return;
        await busy(button, async () => { await api(path, { method: "POST" }); refresh(); });
      });
      return button;
    };

    function parts(ts) {
      if (!ts.installed && !ts.busy) return [action("ts.install", "/api/system/tailscale/install", "ts.install_text")];
      const out = [];
      if (ts.state === "Running") {
        out.push(el("div", { class: "rows" }, row(t("ts.tailnet"), ts.tailnet || "-"), row(t("ts.name"), ts.name || "-"),
          row(t("ts.address"), ts.addresses[0] || "-")),
        el("div", { class: "btnrow" }, action("ts.disconnect", "/api/system/tailscale/disconnect", null, "quiet")));
      } else if (ts.auth_url && ts.auth_url.startsWith("https://")) {
        out.push(el("div", { class: "callout wr", text: t("ts.login_hint") }),
          el("div", { class: "btnrow" }, el("a", { class: "linkbtn", href: ts.auth_url, target: "_blank", rel: "noopener noreferrer" }, t("ts.login"))));
      } else if (ts.installed && !ts.busy) {
        out.push(el("div", { class: "btnrow" }, action("ts.connect", "/api/system/tailscale/connect")));
      }
      if (ts.lines.length && (ts.busy || (ts.exit !== null && ts.exit !== 0) || ts.state !== "Running")) {
        if (ts.exit !== null && ts.exit !== 0) out.push(el("div", { class: "callout bd", text: t("ts.failed") }));
        const box = el("div", { class: "log", text: ts.lines.join("\n") });
        out.push(box);
        requestAnimationFrame(() => { box.scrollTop = box.scrollHeight; });
      }
      return out;
    }

    async function refresh() {
      clearTimeout(timer);
      if (!card.isConnected && timer !== null) return;  // the page was left
      try {
        const ts = (await api("/api/system/tailscale")).tailscale;
        body.replaceChildren(...parts(ts));
        if (ts.busy || WAITING.includes(ts.state)) timer = setTimeout(refresh, POLL_MS);
      } catch (e) {
        if (e.code !== "login_required") toast(errorText(e), true);
      }
    }

    refresh();
    card.stop = () => clearTimeout(timer);
    return card;
  }

  SSPro.views = Object.assign(SSPro.views || {}, { tailscaleCard });
})();
