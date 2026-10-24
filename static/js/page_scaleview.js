/* SpoolmanScale Pro - the paired scale's own web interface in a frame,
 * served by this Pi on its own port (scale_proxy.py), so one address is
 * enough for everything.
 */
(function () {
  "use strict";
  const { t, el, api, toast, errorText } = SSPro;

  function render(main) {
    api("/api/scale").then((data) => {
      const scale = data.scale;
      if (!scale.paired) {
        main.append(el("section", { class: "card" }, el("p", { class: "hint", text: t("view.not_paired") }),
          el("div", { class: "btnrow" }, el("a", { class: "linkbtn", href: "#scale" }, t("view.pair")))));
        return;
      }
      const url = location.protocol + "//" + location.hostname + ":" + scale.proxy_port + "/";
      main.append(
        el("div", { class: "inrow" }, el("p", { class: "hint", text: t("view.hint") }),
          el("a", { class: "linkbtn", href: url, target: "_blank", rel: "noopener" }, t("view.new_tab"))),
        el("iframe", { class: "scaleframe", src: url, title: t("nav.scaleview") }));
    }).catch((e) => { if (e.code !== "login_required") toast(errorText(e), true); });
  }

  SSPro.pages.scaleview = { nav: "nav.scaleview", render };
})();
