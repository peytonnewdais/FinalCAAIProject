/* Runs before Dash renders: pick the theme so the first paint is already correct.
   dcc.Store(id="theme", storage_type="local") keeps its value in
   localStorage["theme"] as JSON, so seeding that key here means the store
   (and every chart callback) starts with a concrete "light" / "dark" value. */
(function () {
  var theme = null;
  try {
    var stored = window.localStorage.getItem("theme");
    theme = stored ? JSON.parse(stored) : null;
    if (theme !== "light" && theme !== "dark") {
      var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
      theme = prefersDark ? "dark" : "light";
      window.localStorage.setItem("theme", JSON.stringify(theme));
      window.localStorage.setItem("theme-timestamp", String(Date.now()));
    }
  } catch (err) {
    theme = "light";
  }
  document.documentElement.setAttribute("data-theme", theme);
})();
