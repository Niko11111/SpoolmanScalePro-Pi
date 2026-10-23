/* SpoolmanScale Pro - the scale card and the Pi card of the overview.
 *
 * Pure drawing from /api/scale and /api/system, like view_backends.js.
 */
(function () {
  "use strict";
  const { t, el, api, busy, toast, formatDuration, formatClock } = SSPro;

  // Above this, the Pi's clock is called wrong and the page offers the
  // browser's time. A Pi has no battery clock, so after a power cut without
  // network it starts from the last saved time.
  const CLOCK_DRIFT_LIMIT_S = 120;
  // RAM above these shares turns the meter yellow, then red.
  const RAM_WARN_SHARE = 0.8;
  const RAM_BAD_SHARE = 0.92;
  const MIB_PER_GIB = 1024;

  function row(label, value, mono) {
    return el("div", { class: "row" }, el("span", { class: "k", text: label }),
      el("span", { class: "v" + (mono ? " mono" : "") }, value));
  }

  function yesNo(flag) {
    return el("span", { class: "pill " + (flag ? "ok" : "wr") }, t(flag ? "common.yes" : "common.no"));
  }

  function scaleCard(scale, onChange) {
    const card = el("section", { class: "card" }, el("h2", { text: t("scale.title") }));
    if (!scale.paired) {
      card.append(el("p", { class: "hint", text: t("scale.not_paired") }),
        el("div", { class: "btnrow" }, el("a", { class: "linkbtn", href: "#scale" }, t("scale.pair"))));
      return card;
    }
    if (!scale.reachable) {
      card.append(el("div", { class: "rows" }, row(t("scale.address"), scale.address, true),
        row(t("scale.state"), el("span", { class: "pill bd" }, t("scale.unreachable")))),
        el("div", { class: "callout bd", text: t("err." + scale.error) }));
      return card;
    }
    card.append(el("div", { class: "rows" },
      row(t("scale.address"), scale.address, true),
      row(t("scale.backend"), scale.backend),
      row(t("scale.reached"), yesNo(scale.backend_ok)),
      row(t("scale.points_here"), yesNo(scale.points_here)),
      row(t("scale.weight"), scale.weight + " g", true),
      row(t("scale.firmware"), scale.version, true)));
    if (!scale.on_active || !scale.points_here) {
      const sync = el("button", { type: "button", class: "block" }, t("scale.sync"));
      sync.addEventListener("click", () => busy(sync, async () => {
        await api("/api/scale/sync", { method: "POST" });
        onChange();
      }));
      card.append(el("div", { class: "callout wr", text: t(scale.on_active ? "warn.scale_points_elsewhere" : "scale.other_backend") }), sync);
    }
    return card;
  }

  function meter(used, total) {
    const share = total ? used / total : 0;
    const level = share > RAM_BAD_SHARE ? " bd" : share > RAM_WARN_SHARE ? " wr" : "";
    const bar = el("i", {});
    // The one inline style of the page: a width only known at run time. Set
    // through the CSSOM, which the Content-Security-Policy allows.
    bar.style.width = Math.round(share * 100) + "%";
    return el("div", { class: "meter" + level }, bar);
  }

  function mib(value) {
    return value >= MIB_PER_GIB ? (value / MIB_PER_GIB).toFixed(1) + " GiB" : value + " MiB";
  }

  // Nothing when the Pi's clock is right; a warning and the button that
  // fixes it when it is not.
  function clockFix(system, onChange) {
    const drift = Math.round(Date.now() / 1000) - system.clock_epoch_s;
    if (Math.abs(drift) <= CLOCK_DRIFT_LIMIT_S) return [];
    const take = el("button", { type: "button", class: "block" }, t("system.take_clock"));
    take.addEventListener("click", () => busy(take, async () => {
      await api("/api/system/clock", { method: "POST", body: { epoch_s: Math.round(Date.now() / 1000) } });
      toast(t("system.clock_set"));
      onChange();
    }));
    return [el("div", { class: "callout wr", text: t("system.clock_off", { min: Math.round(Math.abs(drift) / 60) }) }), take];
  }

  function systemCard(system, onChange) {
    const memory = system.memory;
    const disk = system.disk;
    const rows = el("div", { class: "rows" });
    if (memory) {
      rows.append(el("div", { class: "row" }, el("span", { class: "k", text: t("system.ram") }),
        el("span", { class: "v" }, mib(memory.ram_used_mib) + " / " + mib(memory.ram_total_mib), meter(memory.ram_used_mib, memory.ram_total_mib))));
      if (memory.swap_total_mib) rows.append(row(t("system.swap"), mib(memory.swap_used_mib) + " / " + mib(memory.swap_total_mib)));
    }
    if (disk) rows.append(row(t("system.disk"), mib(disk.disk_used_mib) + " / " + mib(disk.disk_total_mib)));
    rows.append(
      row(t("system.temp"), system.cpu_temp_c === null ? "-" : system.cpu_temp_c + " °C"),
      row(t("system.uptime"), formatDuration(system.uptime_s)),
      row(t("system.clock"), formatClock(system.clock_epoch_s)));
    return el("section", { class: "card" }, el("h2", { text: t("system.title_short") }), rows, clockFix(system, onChange));
  }

  SSPro.views = Object.assign(SSPro.views || {}, { scaleCard, systemCard });
})();
