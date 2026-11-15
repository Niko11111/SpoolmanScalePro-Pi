/* SpoolmanScale Pro - icons on buttons. Each button shows a small icon
 * before its text, so its kind reads at a glance: a tick saves, a bin
 * deletes, a cloud installs. One meaning, one icon, everywhere; where
 * TheRentalScale has the same meaning it uses the same icon.
 *
 * ACTION_ICONS below is the ONE place that decides which button gets which
 * icon, by the button's text key. A button is built with
 * el("button", {...}, label("key")); tests/test_icons.py holds every button
 * to that. The drawings come from icon_data.js (tools/build_icons.py).
 */
(function () {
  "use strict";
  const { t, el } = SSPro;

  const SVG_NS = "http://www.w3.org/2000/svg";

  // Text key of a button -> the icon's name in icon_data.js.
  const ACTION_ICONS = {
    "common.cancel": "close", "common.close": "close",
    "backup.make": "archive", "backup.upload_restore": "upload", "backup.restore": "undo",
    "backup.delete": "delete", "backup.download": "download",
    "demo.reset": "undo", "demo.save": "ok", "demo.import": "upload",
    "net.name_save": "ok", "net.join": "network", "net.connected": "network", "net.choose": "next",
    "net.forget": "delete", "net.scan": "search", "net.manual": "keyboard",
    "net.hotspot_on": "hotspot_on", "net.hotspot_restart": "ok", "net.hotspot_off": "hotspot_off",
    "ip.copy": "copy", "ip.fix_other": "pin", "ip.keep": "pin", "ip.check": "search", "ip.to_dhcp": "undo",
    "pair.take": "ok", "pair.save_test": "ok", "pair.search": "search", "pair.forget_password": "delete",
    "keys.filaman_run": "key", "keys.bambuddy_send": "send", "setup.run": "link",
    "view.pair": "link", "view.new_tab": "external", "scale.pair": "link",
    "setup.back": "back", "setup.skip": "skip", "setup.next": "next", "setup.finish": "home", "setup.open": "wizard",
    "account.save": "ok", "account.switch_off": "unlocked", "account.switch_on": "locks",
    "power.reboot": "reboot", "power.poweroff": "power", "os.restart_now": "reboot",
    "upd.install": "update", "upd.install_version": "update", "os.install": "update", "upd.search": "refresh", "upd.search_all": "refresh",
    "os.search": "refresh", "app.rollback": "undo", "daily.switch": "daily", "daily.leave": "undo",
    "tile.open": "external", "info.homepage": "external", "tile.activate": "switch", "tile.start": "play",
    "par.start": "play", "tile.use": "scale", "tile.stop": "stop", "backends.stop_all": "stop",
    "tile.login": "key", "tile.log": "file", "tile.info": "info",
    "gate.set": "login", "gate.login": "login", "gate.open_button": "unlocked",
    "scale.sync": "refresh", "system.take_clock": "clock",
    "common.show_all": "expand", "common.show_less": "collapse", "upd.notes_more": "expand",
    "app.rollback_go": "undo",
    "ts.install": "download", "ts.connect": "plug", "ts.disconnect": "unplug", "ts.login": "external",
  };
  // Icons that point onwards stand after the text, like "Next >".
  const TRAILING = new Set(["next"]);

  function icon(name) {
    const shapes = SSPro.iconData[name];
    if (!shapes) return null;
    const svg = document.createElementNS(SVG_NS, "svg");
    for (const [attr, value] of [["viewBox", "0 0 24 24"], ["class", "ico ico-" + name], ["aria-hidden", "true"], ["focusable", "false"]]) {
      svg.setAttribute(attr, value);
    }
    for (const [tag, attrs] of shapes) {
      const shape = document.createElementNS(SVG_NS, tag);
      for (const [attr, value] of Object.entries(attrs)) shape.setAttribute(attr, value);
      svg.append(shape);
    }
    return svg;
  }

  function withIcon(name, text) {
    const svg = name ? icon(name) : null;
    if (!svg) return [text];
    return TRAILING.has(name) ? [text, svg] : [svg, text];
  }

  // A button's content: its icon and its text.
  function label(key, vars) {
    return withIcon(ACTION_ICONS[key], t(key, vars));
  }

  // For a button that only gets its finished text (the confirm button of
  // ask()): the icon of the key whose text it is, placeholders included.
  function labelForText(text) {
    const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const key = Object.keys(ACTION_ICONS).find((k) => {
      const pattern = escape(t(k)).replace(/\\\{\w+\\\}/g, ".+");
      return new RegExp("^" + pattern + "$").test(text);
    });
    return withIcon(key && ACTION_ICONS[key], text);
  }

  // A button that is only its icon (copy, beside a value): its name goes to
  // screen readers and the tooltip.
  function iconButton(name, nameKey) {
    return el("button", { type: "button", class: "quiet icon", "aria-label": t(nameKey), title: t(nameKey) }, icon(name));
  }

  Object.assign(SSPro, { icon, label, labelForText, iconButton });
})();
