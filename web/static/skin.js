/* Screen switch for the three FORKU2BTC desks. No remote calls. */
(function forkuSkin() {
  const panels = Array.prototype.slice.call(
    document.querySelectorAll("[data-screen-panel]"),
  );
  const buttons = Array.prototype.slice.call(
    document.querySelectorAll("[data-screen]"),
  );
  if (!panels.length || !buttons.length) return;

  function show(name) {
    let known = false;
    panels.forEach(function (panel) {
      const on = panel.getAttribute("data-screen-panel") === name;
      panel.classList.toggle("is-on", on);
      if (on) known = true;
    });
    if (!known) name = "create";
    buttons.forEach(function (button) {
      const on = button.getAttribute("data-screen") === name;
      button.setAttribute("aria-pressed", on ? "true" : "false");
    });
    document.body.classList.add("app-ready");
  }

  function fromHash() {
    const hash = (location.hash || "").replace("#", "");
    if (hash === "receive" || hash === "settle" || hash === "create") return hash;
    return "create";
  }

  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      const name = button.getAttribute("data-screen") || "create";
      if (location.hash !== "#" + name) location.hash = name;
      else show(name);
    });
  });

  window.addEventListener("hashchange", function () {
    show(fromHash());
  });

  show(fromHash());
})();
