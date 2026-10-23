/* SpoolmanScale Pro - the row of project links under every page, the same
 * four the scale's web interface shows (SpoolmanScale web_shell.cpp).
 *
 * GitHub and Discord publish monochrome marks; Ko-fi and MakerWorld get a
 * plain heart and a plain cube instead of a redrawn logo. Each icon takes
 * the colour of its button (fill: currentColor in app.css).
 */
(function () {
  "use strict";
  const { t, el } = SSPro;

  const SVG_NS = "http://www.w3.org/2000/svg";
  const LINKS = [
    { label: "GitHub", href: "https://github.com/Niko11111/SpoolmanScale",
      path: "M12 .5C5.37.5 0 5.87 0 12.5c0 5.3 3.44 9.8 8.21 11.39.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.73.08-.73 1.2.08 1.84 1.24 1.84 1.24 1.07 1.84 2.81 1.31 3.5 1 .11-.78.42-1.31.76-1.61-2.67-.3-5.47-1.34-5.47-5.96 0-1.32.47-2.39 1.24-3.23-.12-.31-.54-1.53.12-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 016.01 0c2.29-1.55 3.3-1.23 3.3-1.23.66 1.65.24 2.87.12 3.18.77.84 1.24 1.91 1.24 3.23 0 4.63-2.81 5.65-5.49 5.95.43.37.82 1.1.82 2.22v3.29c0 .32.22.7.83.58A12.01 12.01 0 0024 12.5C24 5.87 18.63.5 12 .5z" },
    { labelKey: "links.kofi", short: "Ko-fi", support: true, href: "https://ko-fi.com/formfollowsfunction",
      path: "M12 21s-6.7-4.35-9.1-7.8C.6 10.1 2.1 6 5.8 6c2 0 3.4 1.1 4.2 2.2C10.8 7.1 12.2 6 14.2 6c3.7 0 5.2 4.1 2.9 7.2C18.7 16.65 12 21 12 21z" },
    { label: "Discord", href: "https://discord.gg/K3KmKnrWhP",
      path: "M20.3 4.4a19.8 19.8 0 00-4.9-1.5l-.6 1.2a18.3 18.3 0 00-5.5 0l-.6-1.2a19.7 19.7 0 00-4.9 1.5C.5 9 -.3 13.6.1 18a19.9 19.9 0 006 3l1.2-2a13.1 13.1 0 01-1.9-.9l.4-.3a14 14 0 0012.1 0l.4.3a13 13 0 01-1.9.9l1.2 2a19.8 19.8 0 006-3c.5-5.2-.8-9.7-3.5-13.6zM8 15.3c-1.2 0-2.2-1.1-2.2-2.4S6.8 10.5 8 10.5s2.2 1.1 2.2 2.4S9.2 15.3 8 15.3zm8 0c-1.2 0-2.2-1.1-2.2-2.4s1-2.4 2.2-2.4 2.2 1.1 2.2 2.4-1 2.4-2.2 2.4z" },
    { label: "MakerWorld", href: "https://makerworld.com/de/@FormFollowsF/upload",
      path: "M12 2.5l8.5 4.75v9.5L12 21.5l-8.5-4.75v-9.5L12 2.5zm0 2.29L6.06 8.1 12 11.4l5.94-3.3L12 4.79zM5.5 9.79v5.79l5.5 3.07v-5.79L5.5 9.79zm13 0l-5.5 3.07v5.79l5.5-3.07V9.79z" },
  ];

  function icon(d) {
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    svg.append(path);
    return svg;
  }

  function linkButton(link) {
    // Ko-fi carries the long label and falls back to its name where the
    // long one does not fit (.lg / .sm in app.css).
    const label = link.labelKey
      ? [el("span", { class: "lg", text: t(link.labelKey) }), el("span", { class: "sm", text: link.short })]
      : link.label;
    return el("a", { href: link.href, target: "_blank", rel: "noopener", class: link.support ? "support" : null },
      icon(link.path), label);
  }

  function linksRow() {
    return el("div", { class: "links" }, LINKS.map(linkButton));
  }

  SSPro.views = Object.assign(SSPro.views || {}, { linksRow });
})();
