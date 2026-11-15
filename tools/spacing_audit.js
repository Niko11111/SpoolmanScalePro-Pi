/* Spacing audit for the web page: finds buttons and boxes that touch.
 *
 * Paste into the browser console on a page of SpoolmanScale Pro (dev server
 * or Pi). It walks every page in the navigation and lists each pair of
 * stacked neighbours inside a card where one is a button or a box and the
 * gap between them is under MIN_GAP_PX. Field labels over their input and
 * rows of one list are 7 px on purpose and are left out.
 *
 * Found by it on 15.11.2026: the error callout on the tiles, a button row on
 * a field, the IP check message on its field (each 0 px).
 */
(async function () {
  "use strict";
  const MIN_GAP_PX = 8;
  const PAGE_WAIT_MS = 1800;
  const BOXY = "button, .linkbtn, .callout, .listrow, .tile, .tiles, input, select, textarea, .rows, .btnrow, " +
    ".netlist, details, .release, .notes, .msg:not(:empty), .card .card";
  const INTENDED = /LABEL -> |-> hint|listrow -> listrow/;

  function tightPairs(card, out) {
    const title = (card.querySelector("h2, h3") || {}).textContent || "?";
    const walk = (parent) => {
      const kids = [...parent.children].filter((k) => k.offsetParent && getComputedStyle(k).position !== "absolute");
      for (let i = 1; i < kids.length; i++) {
        const above = kids[i - 1].getBoundingClientRect();
        const below = kids[i].getBoundingClientRect();
        if (below.top < above.bottom - 1 || !(kids[i - 1].matches(BOXY) || kids[i].matches(BOXY))) continue;
        const gap = Math.round(below.top - above.bottom);
        const line = `${title.slice(0, 30)} | ${kids[i - 1].className || kids[i - 1].tagName} -> ${kids[i].className || kids[i].tagName} = ${gap}px`;
        if (gap < MIN_GAP_PX && !INTENDED.test(line)) out.push(line);
      }
      kids.forEach(walk);
    };
    walk(card);
  }

  const found = {};
  for (const page of Object.keys(SSPro.pages)) {
    location.hash = "#" + page;
    await new Promise((resolve) => setTimeout(resolve, PAGE_WAIT_MS));
    const out = [];
    for (const card of document.querySelectorAll("section.card, form.card, dialog[open]")) tightPairs(card, out);
    if (out.length) found[page] = out;
  }
  console.log(Object.keys(found).length ? found : "spacing audit: nothing touches");
})();
