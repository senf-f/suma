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

  document.addEventListener("click", function (event) {
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
      bundlePath: (window.SUMA_ROOT || "") + "pagefind/",
      showSubResults: true,
      translations: { placeholder: "Pretraži tekst", zero_results: "Nema rezultata za [SEARCH_TERM]" },
    });
  }
})();
