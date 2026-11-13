// When a word has no match, Pagefind searches for a shorter prefix of it instead, so "supplementum"
// returns every page with "su". accepts() keeps a result only if, for every word typed, one of the
// highlighted words starts with it, or is a prefix of it at least 4 letters and 60% of its length long
// (an inflected form falling back to its stem, e.g. "sakramentima" to "sakrament").
(function (root) {
  function normalize(word) {
    return word.toLowerCase().replace(/đ/g, "d").normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/[^\p{L}\p{N}]/gu, "");
  }

  function termMatches(term, words) {
    return words.some(function (w) {
      return w.startsWith(term) || (term.startsWith(w) && w.length >= 4 && w.length >= 0.6 * term.length);
    });
  }

  function accepts(query, markedWords) {
    var terms = query.split(/\s+/).map(normalize).filter(Boolean);
    var words = markedWords.map(normalize).filter(Boolean);
    return terms.every(function (t) { return termMatches(t, words); });
  }

  // The words Pagefind matched anywhere on the page: its locations index the page text's words.
  // (The excerpt shows only one passage, which may not contain every word of a multi-word query.)
  function matchedWords(data) {
    var words = (data.content || "").split(/\s+/);
    return (data.locations || []).map(function (i) { return words[i] || ""; });
  }

  var api = { accepts: accepts, matchedWords: matchedWords, normalize: normalize };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.SumaSearch = api;
})(this);
