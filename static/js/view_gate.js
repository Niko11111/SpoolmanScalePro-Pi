/* SpoolmanScale Pro - the gate in front of the page: the first visit, which
 * creates the account (or decides to run without one), and the login.
 *
 * The form has a user name and a password field with the autocomplete
 * names password managers look for, so they offer to store and fill them.
 */
(function () {
  "use strict";
  const { t, el, api, ask, errorText } = SSPro;

  const DEFAULT_USERNAME = "admin";

  function field(labelKey, input) {
    return el("div", { class: "field" }, el("label", { text: t(labelKey) }), input);
  }

  async function runWithoutPassword(onDone, message) {
    if (!(await ask(t("gate.open_title"), t("gate.open_text"), t("gate.open_confirm"), true))) return;
    try {
      await api("/api/auth/setup", { method: "POST", body: { open: true } });
      onDone();
    } catch (err) {
      message.textContent = errorText(err);
    }
  }

  // firstVisit: create the account; otherwise log in. onDone: called once
  // the visitor is in.
  function gateForm(firstVisit, onDone) {
    const user = el("input", { type: "text", name: "username", autocomplete: "username",
      autocapitalize: "none", spellcheck: "false", required: true, value: firstVisit ? DEFAULT_USERNAME : "" });
    const pass = el("input", { type: "password", name: "password", required: true,
      autocomplete: firstVisit ? "new-password" : "current-password" });
    const message = el("div", { class: "msg bad", role: "alert" });
    const submit = el("button", { class: "block", type: "submit" }, t(firstVisit ? "gate.set" : "gate.login"));
    const form = el("form", { class: "card", method: "post", action: "#" },
      el("h2", { text: t(firstVisit ? "gate.setup_title" : "gate.login_title") }),
      firstVisit ? el("p", { class: "hint", text: t("gate.setup_hint") }) : null,
      field("gate.username", user), field("gate.password", pass), message, submit);
    if (firstVisit) {
      form.append(el("button", { class: "quiet block", type: "button",
        onclick: () => runWithoutPassword(onDone, message) }, t("gate.open_button")));
    }
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      submit.disabled = true;
      try {
        await api(firstVisit ? "/api/auth/setup" : "/api/auth/login",
          { method: "POST", body: { username: user.value, password: pass.value } });
        onDone();
      } catch (err) {
        message.textContent = errorText(err);
        submit.disabled = false;
      }
    });
    return { form, focus: firstVisit ? pass : user };
  }

  SSPro.views = Object.assign(SSPro.views || {}, { gateForm });
})();
