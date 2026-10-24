/* SpoolmanScale Pro - release notes from GitHub, readable without letting
 * any of their markup into the page.
 *
 * The notes are Markdown written by the backends' authors. A small subset
 * becomes real elements (headings, list items, links, bold); everything is
 * placed as text, so nothing in a note is ever parsed as HTML. Links are
 * kept only when they point to https.
 */
(function () {
  "use strict";
  const { t, el } = SSPro;

  // A note longer than this is cut; the full one is a click away on GitHub.
  const MAX_LINES = 60;
  const INLINE_RE = /\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)/g;

  function inline(text) {
    const parts = [];
    let last = 0;
    for (const m of text.matchAll(INLINE_RE)) {
      if (m.index > last) parts.push(text.slice(last, m.index));
      if (m[1]) parts.push(el("b", { text: m[1] }));
      else if (m[2]) parts.push(el("code", { text: m[2] }));
      else if (m[4].startsWith("https://")) parts.push(el("a", { href: m[4], target: "_blank", rel: "noopener noreferrer", text: m[3] }));
      else parts.push(m[3]);
      last = m.index + m[0].length;
    }
    if (last < text.length) parts.push(text.slice(last));
    return parts;
  }

  function lineNode(line) {
    const heading = line.match(/^#{1,6}\s+(.*)$/);
    if (heading) return el("p", { class: "note-h" }, inline(heading[1]));
    const item = line.match(/^\s*[-*+]\s+(.*)$/);
    if (item) return el("p", { class: "note-li" }, inline(item[1]));
    return el("p", {}, inline(line));
  }

  function body(markdown) {
    const lines = markdown.replace(/\r/g, "").split("\n").filter((l) => l.trim() && !/^\s*(<!--.*-->|---+)\s*$/.test(l));
    const nodes = lines.slice(0, MAX_LINES).map(lineNode);
    if (lines.length > MAX_LINES) nodes.push(el("p", { class: "hint", text: t("upd.notes_cut") }));
    return el("div", { class: "notes" }, nodes);
  }

  // One release as a fold-out: name and date, then the notes.
  function releaseNotes(release, open) {
    const head = el("summary", {}, el("b", { text: release.name || release.tag }),
      release.published ? " - " + release.published : "",
      release.prerelease ? el("span", { class: "pill wr" }, t("upd.prerelease")) : null);
    const link = release.url && release.url.startsWith("https://")
      ? el("a", { href: release.url, target: "_blank", rel: "noopener noreferrer", text: t("upd.on_github") }) : null;
    return el("details", { class: "release", open: open }, head, body(release.body || ""), link);
  }

  SSPro.views = Object.assign(SSPro.views || {}, { releaseNotes });
})();
