(function () {
  function load(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { /* storage unavailable */ }
  }

  var body = document.body;

  var latinToggle = document.getElementById("latin-toggle");
  if (latinToggle) {
    var hideLatin = load("suma.hideLatin") === "1";
    latinToggle.checked = !hideLatin;
    body.classList.toggle("hide-la", hideLatin);
    latinToggle.addEventListener("change", function () {
      body.classList.toggle("hide-la", !latinToggle.checked);
      save("suma.hideLatin", latinToggle.checked ? "0" : "1");
    });
  }

  var modelSwitch = document.getElementById("model-switch");
  function showModel(model) {
    document.querySelectorAll("[data-model]").forEach(function (el) {
      el.hidden = el.getAttribute("data-model") !== model;
    });
  }
  if (modelSwitch) {
    var savedModel = load("suma.model");
    var known = Array.prototype.some.call(modelSwitch.options, function (o) { return o.value === savedModel; });
    if (known) modelSwitch.value = savedModel;
    showModel(modelSwitch.value);
    modelSwitch.addEventListener("change", function () {
      showModel(modelSwitch.value);
      save("suma.model", modelSwitch.value);
    });
  }

  // A: a paragraph's actions open from its "⋯" button.
  function setOpen(unit, open) {
    unit.classList.toggle("open", open);
    unit.querySelector(".more").setAttribute("aria-expanded", open ? "true" : "false");
  }

  // B: light/dark switch, overriding the system setting once chosen.
  var root = document.documentElement;
  function currentTheme() {
    var chosen = root.getAttribute("data-theme");
    if (chosen) return chosen;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  var themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      save("suma.theme", next);
    });
  }

  // B: search lives behind the magnifier.
  var search = document.getElementById("search");
  var searchToggle = document.getElementById("search-toggle");
  function setSearch(open) {
    search.hidden = !open;
    searchToggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      var input = search.querySelector("input");
      if (input) input.focus();
    }
  }
  if (search && searchToggle) {
    searchToggle.addEventListener("click", function () { setSearch(search.hidden); });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !search.hidden) { setSearch(false); searchToggle.focus(); }
    });
  }

  // B: the header slides away while scrolling down and returns on the way up.
  var header = document.querySelector("header.site");
  var lastY = window.scrollY;
  window.addEventListener("scroll", function () {
    var y = window.scrollY;
    var hide = y > lastY && y > 120 && search.hidden;
    header.classList.toggle("tucked", hide);
    lastY = y;
  }, { passive: true });

  document.addEventListener("click", function (event) {
    var more = event.target.closest(".more");
    if (more) {
      var unit = more.closest(".unit");
      setOpen(unit, !unit.classList.contains("open"));
      return;
    }
    var laButton = event.target.closest(".la-btn");
    if (laButton) {
      laButton.closest(".unit").classList.toggle("show-la");
      return;
    }
    var citeButton = event.target.closest(".cite");
    if (!citeButton) return;
    var text = citeButton.getAttribute("data-cite");
    var original = citeButton.textContent;
    function copied() {
      citeButton.textContent = "Kopirano";
      setTimeout(function () { citeButton.textContent = original; }, 1500);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(copied, function () { window.prompt("Citat:", text); });
    } else {
      window.prompt("Citat:", text);
    }
  });

  if (window.PagefindUI) {
    new PagefindUI({
      element: "#search",
      // A full URL: import() rejects a bare "pagefind/" on top-level pages, where SUMA_ROOT is "".
      bundlePath: new URL((window.SUMA_ROOT || "") + "pagefind/", document.baseURI).href,
      showSubResults: true,
      translations: { placeholder: "Pretraži prijevod", zero_results: "Nema rezultata za [SEARCH_TERM]" },
    });
  }
})();
