/* SpoolmanScale Pro - layout pieces several pages share.
 *
 * columns(): two columns that stack their cards on their own. In a grid,
 * each card grew to the height of the one beside it, so a short card stood
 * half empty next to a long one. The most important cards go first in the
 * left column; on a phone the columns run one after the other, left first.
 *
 * collapsed(): a long list shows its first few rows and a button for the
 * rest.
 *
 * copyable(): a value with a copy button beside it.
 */
(function () {
  "use strict";
  const { t, el, label, toast, copyText, iconButton } = SSPro;

  function columns(left, right) {
    return el("div", { class: "cols" }, el("div", { class: "col" }, left), el("div", { class: "col" }, right));
  }

  // rows: nodes; shown: how many stay visible. The button names the count.
  function collapsed(rows, shown) {
    if (rows.length <= shown) return rows;
    const rest = el("div", { class: "more", hidden: true }, rows.slice(shown));
    const toggle = el("button", { type: "button", class: "quiet" }, label("common.show_all", { count: rows.length }));
    toggle.addEventListener("click", () => {
      rest.hidden = !rest.hidden;
      toggle.replaceChildren(...(rest.hidden ? label("common.show_all", { count: rows.length }) : label("common.show_less")));
    });
    return [...rows.slice(0, shown), rest, el("div", { class: "btnrow" }, toggle)];
  }

  // A value with a copy button beside it (a generated password). Where the
  // browser refuses to copy, the toast shows the value to copy by hand.
  function copyable(text, mono) {
    const copy = iconButton("copy", "common.copy");
    copy.addEventListener("click", async () => toast((await copyText(text)) ? t("common.copied") : text));
    return el("span", { class: "v copyable" }, el("span", { class: mono ? "mono" : "", text: text }), copy);
  }

  SSPro.views = Object.assign(SSPro.views || {}, { columns, collapsed, copyable });
})();
