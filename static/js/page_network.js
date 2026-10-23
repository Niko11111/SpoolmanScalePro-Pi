/* SpoolmanScale Pro - the Pi's network: its name (<name>.local), the WLAN
 * it is in, and its own WLAN (hotspot). Every change can cut this page off,
 * so each one asks first and says where the Pi will be afterwards.
 */
(function () {
  "use strict";
  const { t, el, api, ask, busy, toast, errorText, views } = SSPro;

  const CHANNELS = [1, 6, 11];
  const HOSTNAME_PATTERN = "[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?";

  function row(label, value, mono) {
    return el("div", { class: "row" }, el("span", { class: "k", text: label }),
      el("span", { class: "v" + (mono ? " mono" : "") }, value));
  }

  function nameCard(net) {
    const name = el("input", { type: "text", value: net.hostname, pattern: HOSTNAME_PATTERN,
      autocapitalize: "none", spellcheck: "false" });
    const save = el("button", { type: "button" }, t("net.name_save"));
    save.addEventListener("click", async () => {
      const next = name.value.trim().toLowerCase();
      if (!(await ask(t("net.name_title"), t("net.name_text", { name: next }), t("net.name_save")))) return;
      await busy(save, async () => {
        await api("/api/network/hostname", { method: "POST", body: { hostname: next } });
        toast(t("net.name_done", { name: next }));
      });
    });
    return el("section", { class: "card" }, el("h2", { text: t("net.name_title") }),
      el("div", { class: "field" }, el("label", { text: t("net.name_label") }),
        el("div", { class: "inrow" }, name, el("span", { class: "mono", text: ".local" }))),
      el("p", { class: "hint", text: t("net.name_hint") }),
      el("div", { class: "btnrow" }, save));
  }

  function modeText(net) {
    const wlan = net.wlan;
    if (wlan.mode === "client") return t("net.mode_client", { name: wlan.connection });
    return t("net.mode_" + wlan.mode, { address: net.hotspot_address });
  }

  function statusRows(net) {
    const rows = [row(t("net.wlan"), modeText(net)),
      row(t("net.cable"), t(net.ethernet ? "common.yes" : "common.no"))];
    for (const [iface, address] of Object.entries(net.addresses)) rows.push(row(iface, address, true));
    return el("div", { class: "rows" }, rows);
  }

  function joinForm(network, start) {
    const psk = el("input", { type: "password", autocomplete: "off", placeholder: t(network.secure ? "net.psk" : "net.psk_open") });
    const join = el("button", { type: "button" }, t("net.join"));
    join.addEventListener("click", async () => {
      if (!(await ask(t("net.join_title", { name: network.ssid }), t("net.join_text"), t("net.join")))) return;
      start(join, "/api/network/wifi", { ssid: network.ssid, psk: psk.value });
    });
    return el("div", { class: "inrow" }, network.secure ? psk : null, join);
  }

  function networkRow(network, start) {
    const holder = el("div", {});
    const pick = el("button", { type: "button", class: "quiet", disabled: network.in_use },
      t(network.in_use ? "net.connected" : "net.choose"));
    pick.addEventListener("click", () => holder.replaceChildren(joinForm(network, start)));
    return el("div", { class: "listrow" },
      el("div", {}, el("div", { class: "nm", text: network.ssid }),
        el("div", { class: "sz", text: network.signal + " %" + (network.secure ? "" : " - " + t("net.open")) })),
      pick, holder);
  }

  function wifiCard(net, start) {
    const list = el("div", { class: "wrap" });
    const scan = el("button", { type: "button", class: "quiet" }, t("net.scan"));
    scan.addEventListener("click", () => busy(scan, async () => {
      list.replaceChildren(el("p", { class: "hint", text: t("net.scanning") }));
      const found = (await api("/api/network/scan", { method: "POST" })).networks;
      list.replaceChildren(...(found.length ? found.map((n) => networkRow(n, start))
        : [el("p", { class: "hint", text: t("net.none_found") })]));
    }));
    return el("section", { class: "card" }, el("h2", { text: t("net.wifi_title") }), statusRows(net),
      el("div", { class: "btnrow" }, scan), list, el("p", { class: "note", text: t("net.wifi_note") }));
  }

  function hotspotCard(net, start) {
    const on = net.wlan.mode === "hotspot";
    const ssid = el("input", { type: "text", value: net.hotspot_ssid || "SpoolmanScale-Pro", autocomplete: "off" });
    const psk = el("input", { type: "password", autocomplete: "new-password", placeholder: t("net.hotspot_psk_hint") });
    const channel = el("select", {}, CHANNELS.map((c) => el("option", { value: c, selected: c === net.hotspot_channel }, String(c))));
    const startButton = el("button", { type: "button" }, t(on ? "net.hotspot_restart" : "net.hotspot_on"));
    startButton.addEventListener("click", async () => {
      if (!(await ask(t("net.hotspot_title"), t("net.hotspot_on_text", { address: net.hotspot_address }), t("net.hotspot_on")))) return;
      start(startButton, "/api/network/hotspot", { ssid: ssid.value, psk: psk.value, channel: Number(channel.value) });
    });
    const stop = on ? el("button", { type: "button", class: "danger" }, t("net.hotspot_off")) : null;
    if (stop) {
      stop.addEventListener("click", async () => {
        if (!(await ask(t("net.hotspot_off"), t("net.hotspot_off_text"), t("net.hotspot_off"), true))) return;
        start(stop, "/api/network/hotspot/off");
      });
    }
    return el("section", { class: "card" }, el("h2", { text: t("net.hotspot_title") }),
      el("p", { class: "hint", text: t("net.hotspot_hint") }),
      el("div", { class: "field" }, el("label", { text: t("net.hotspot_ssid") }), ssid),
      el("div", { class: "field" }, el("label", { text: t("net.hotspot_psk") }), psk),
      el("div", { class: "field" }, el("label", { text: t("net.hotspot_channel") }), channel),
      el("div", { class: "btnrow" }, startButton, stop));
  }

  // The address the Pi has on its network, and three ways to keep it:
  // a reservation in the router (recommended, by the MAC shown here), the
  // current address made fixed, or another one checked first.
  function ipRows(ip) {
    const copy = el("button", { type: "button", class: "quiet" }, t("ip.copy"));
    copy.addEventListener("click", () => {
      navigator.clipboard.writeText(ip.mac).then(() => toast(t("ip.copied")), () => toast(ip.mac));
    });
    return el("div", { class: "rows" },
      row(t("ip.connection"), ip.connection),
      row(t("ip.address"), ip.address, true),
      row(t("ip.kind"), t(ip.fixed ? "ip.fixed" : "ip.dhcp")),
      row(t("ip.gateway"), ip.gateway, true),
      row(t("ip.mac"), el("span", { class: "inrow" }, el("span", { class: "mono", text: ip.mac }), copy)));
  }

  function otherAddress(ip, start) {
    const input = el("input", { type: "text", placeholder: ip.address.split("/")[0], inputmode: "decimal" });
    const verdict = el("div", { class: "msg", role: "status" });
    const fix = el("button", { type: "button", disabled: true }, t("ip.fix_other"));
    const check = el("button", { type: "button", class: "quiet" }, t("ip.check"));
    check.addEventListener("click", () => busy(check, async () => {
      const result = (await api("/api/network/ip/check", { method: "POST", body: { address: input.value } })).verdict;
      const free = result === "free";
      verdict.className = "msg" + (free ? "" : " bad");
      verdict.textContent = free ? t("ip.free") : errorText({ code: result === "taken" ? "ip_taken" : result });
      fix.disabled = !free;
    }));
    input.addEventListener("input", () => { fix.disabled = true; verdict.textContent = ""; });
    fix.addEventListener("click", async () => {
      if (!(await ask(t("ip.fix_title", { address: input.value }), t("ip.fix_text", { address: input.value }), t("ip.fix_other")))) return;
      start(fix, "/api/network/ip/static", { address: input.value });
    });
    return [el("div", { class: "field" }, el("label", { text: t("ip.other") }), el("div", { class: "inrow" }, input, check)),
      verdict, el("div", { class: "btnrow" }, fix)];
  }

  function ipCard(ip, start) {
    const card = el("section", { class: "card" }, el("h2", { text: t("ip.title") }));
    if (!ip) {
      card.append(el("p", { class: "hint", text: t("ip.no_uplink") }));
      return card;
    }
    card.append(ipRows(ip), el("p", { class: "hint", text: t("ip.router_hint") }));
    if (ip.fixed) {
      const back = el("button", { type: "button", class: "quiet" }, t("ip.to_dhcp"));
      back.addEventListener("click", async () => {
        if (!(await ask(t("ip.to_dhcp"), t("ip.to_dhcp_text"), t("ip.to_dhcp")))) return;
        start(back, "/api/network/ip/dhcp");
      });
      card.append(el("div", { class: "btnrow" }, back));
      return card;
    }
    const keep = el("button", { type: "button" }, t("ip.keep"));
    keep.addEventListener("click", async () => {
      if (!(await ask(t("ip.keep"), t("ip.keep_text", { address: ip.address.split("/")[0] }), t("ip.keep")))) return;
      start(keep, "/api/network/ip/static", {});
    });
    card.append(el("div", { class: "btnrow" }, keep), ...otherAddress(ip, start),
      el("p", { class: "note", text: t("ip.range_note") }));
    return card;
  }

  function render(main) {
    const jobSlot = el("div", { class: "wrap" });
    const grid = el("div", { class: "grid" });
    main.append(jobSlot, grid);
    let unfollow = null;

    function follow(onlyIfRunning) {
      if (unfollow) unfollow();
      unfollow = views.followJob(jobSlot, (key) => key, draw, onlyIfRunning);
    }

    function start(button, path, body) {
      return busy(button, async () => {
        await api(path, { method: "POST", body: body });
        follow(false);
      });
    }

    async function draw() {
      try {
        const net = (await api("/api/network")).network;
        if (!net.available) {
          grid.replaceChildren(nameCard(net), el("section", { class: "card" }, el("h2", { text: t("net.wifi_title") }),
            el("div", { class: "callout wr", text: t("net.unavailable") })));
          return;
        }
        grid.replaceChildren(nameCard(net), wifiCard(net, start), ipCard(net.ip, start), hotspotCard(net, start));
      } catch (e) {
        if (e.code !== "login_required") toast(errorText(e), true);
      }
    }

    draw().then(() => follow(true));
    return () => { if (unfollow) unfollow(); };
  }

  SSPro.pages.network = { nav: "nav.network", render };
})();
