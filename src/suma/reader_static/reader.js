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

  // Search: our own box on Pagefind's search API rather than Pagefind's ready-made UI, so that results
  // matching only a far shorter prefix of the typed word ("supplementum" -> "su") can be dropped.
  if (search && window.SumaSearch) {
    search.innerHTML =
      '<input type="search" class="search-input" placeholder="Pretraži prijevod" aria-label="Pretraži prijevod" autocomplete="off">' +
      '<p class="search-message" aria-live="polite"></p>' +
      '<ol class="search-results"></ol>' +
      '<button type="button" class="search-more" hidden>Prikaži više</button>';
    var searchInput = search.querySelector(".search-input");
    var searchMessage = search.querySelector(".search-message");
    var searchList = search.querySelector(".search-results");
    var searchMore = search.querySelector(".search-more");
    var PAGE = 10;
    var pagefind = null, searchId = 0, timer = null, found = [], shown = 0, query = "";

    function loadPagefind() {
      // A full URL: import() rejects a bare "pagefind/pagefind.js" on top-level pages, where SUMA_ROOT is "".
      if (!pagefind) {
        pagefind = import(new URL((window.SUMA_ROOT || "") + "pagefind/pagefind.js", document.baseURI).href)
          .then(function (pf) { return pf.options({ excerptLength: 30 }).then(function () { return pf; }); });
      }
      return pagefind;
    }
    function countLabel(n) {
      return n + ((n % 10 === 1 && n % 100 !== 11) ? " rezultat" : " rezultata");
    }
    function escapeText(s) {
      return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }
    function renderResult(data) {
      // Pagefind's excerpts are escaped page text with <mark> around the matches.
      var li = document.createElement("li");
      var html = '<a class="search-title" href="' + escapeText(data.url) + '">' + escapeText(data.meta.title || data.url) + "</a>" +
        '<p class="search-excerpt">' + data.excerpt + "</p>";
      var subs = (data.sub_results || []).filter(function (sub) { return sub.url !== data.url; }).slice(0, 3);
      if (subs.length) {
        html += '<ul class="search-subs">' + subs.map(function (sub) {
          return '<li><a href="' + escapeText(sub.url) + '">' + escapeText(sub.title) + '</a><p class="search-excerpt">' + sub.excerpt + "</p></li>";
        }).join("") + "</ul>";
      }
      li.innerHTML = html;
      searchList.appendChild(li);
    }
    function nothing() {
      searchMessage.textContent = "Nema rezultata za „" + query + "“.";
      searchMore.hidden = true;
    }
    function showMore(id) {
      var batch = found.slice(shown, shown + PAGE);
      shown += batch.length;
      return Promise.all(batch.map(function (r) { return r.data(); })).then(function (datas) {
        if (id !== searchId) return;
        datas.forEach(function (data) { if (SumaSearch.accepts(query, SumaSearch.matchedWords(data))) renderResult(data); });
        searchMore.hidden = shown >= found.length;
      });
    }
    function runSearch(text) {
      var id = ++searchId;
      query = text.trim();
      searchList.innerHTML = "";
      searchMore.hidden = true;
      found = []; shown = 0;
      if (!query) { searchMessage.textContent = ""; return; }
      searchMessage.textContent = "Pretražujem…";
      loadPagefind().then(function (pf) { return pf.search(query); }).then(function (res) {
        if (id !== searchId) return;
        if (!res || !res.results.length) return nothing();
        // Pagefind falls back for the whole result set at once, so the first result tells whether
        // the results contain what was typed or only a far shorter prefix of it.
        return res.results[0].data().then(function (first) {
          if (id !== searchId) return;
          if (!SumaSearch.accepts(query, SumaSearch.matchedWords(first))) return nothing();
          found = res.results;
          searchMessage.textContent = countLabel(found.length) + " za „" + query + "“";
          return showMore(id);
        });
      }).catch(function () {
        if (id === searchId) searchMessage.textContent = "Pretraživanje trenutačno ne radi.";
      });
    }
    searchInput.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () { runSearch(searchInput.value); }, 250);
    });
    searchMore.addEventListener("click", function () { showMore(searchId); });
  }
})();
