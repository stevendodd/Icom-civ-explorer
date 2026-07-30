// Light/dark theme toggle for Icom CI-V Explorer.
// CSP-compliant: external script only (no inline handlers/styles).
// Mirrors the pycom.stevendodd.net theme behaviour: dark is default,
// preference persisted in localStorage under "civ-theme".
(function () {
  "use strict";

  var STORAGE_KEY = "civ-theme";

  function resolveTheme() {
    var stored = null;
    try { stored = localStorage.getItem(STORAGE_KEY); } catch (e) {}
    if (stored === "light" || stored === "dark") return stored;
    return "dark";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var btn = document.querySelector(".theme-toggle");
    if (btn) {
      btn.setAttribute("aria-pressed", String(theme === "light"));
      btn.setAttribute(
        "aria-label",
        theme === "light" ? "Switch to dark theme" : "Switch to light theme"
      );
      btn.title = theme === "light" ? "Switch to dark theme" : "Switch to light theme";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    applyTheme(resolveTheme());
    var btn = document.querySelector(".theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var current =
        document.documentElement.getAttribute("data-theme") || "dark";
      var next = current === "light" ? "dark" : "light";
      try { localStorage.setItem(STORAGE_KEY, next); } catch (e) {}
      applyTheme(next);
    });
  });
})();