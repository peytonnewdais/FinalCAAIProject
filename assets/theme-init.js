/* Runs before Dash renders: pick the display modes so the first paint is already correct.
   dcc.Store(id="theme") and dcc.Store(id="cvd") use storage_type="local", which keeps their
   values in localStorage as JSON, so seeding those keys here means the stores (and every
   chart callback) start with a concrete value instead of null. */
(function () {
  function seed(key, isValid, fallback) {
    var value = null;
    try {
      var stored = window.localStorage.getItem(key);
      value = stored ? JSON.parse(stored) : null;
      if (!isValid(value)) {
        value = fallback();
        window.localStorage.setItem(key, JSON.stringify(value));
        window.localStorage.setItem(key + "-timestamp", String(Date.now()));
      }
    } catch (err) {
      value = fallback();
    }
    return value;
  }

  var theme = seed(
    "theme",
    function (v) { return v === "light" || v === "dark"; },
    function () {
      var prefersDark = window.matchMedia
        && window.matchMedia("(prefers-color-scheme: dark)").matches;
      return prefersDark ? "dark" : "light";
    }
  );

  var cvd = seed(
    "cvd",
    function (v) { return v === true || v === false; },
    function () { return false; }
  );

  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.setAttribute("data-cvd", cvd === true ? "on" : "off");
})();
