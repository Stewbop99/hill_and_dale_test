// Hill and Dale — runner search
//
// Reads whatever <li> entries are already in #runner-list (however many
// runners that is) and filters them as you type. No fetches, no build step:
// it just works against the static HTML the splicer already generated.
//
// Landing page shows nothing by default — only the search box. The list
// appears (filtered) once you start typing, and disappears again if you
// clear the box.

(function () {
  var input = document.getElementById('runner-search');
  var list = document.getElementById('runner-list');
  var noResults = document.getElementById('no-results');

  if (!input || !list || !noResults) return;

  var runners = Array.prototype.slice.call(list.querySelectorAll('li')).map(function (li) {
    return { el: li, name: li.textContent.toLowerCase().trim() };
  });

  function render() {
    var query = input.value.toLowerCase().trim();

    if (query === '') {
      list.style.display = 'none';
      noResults.hidden = true;
      return;
    }

    var matches = 0;
    runners.forEach(function (runner) {
      var isMatch = runner.name.indexOf(query) !== -1;
      runner.el.hidden = !isMatch;
      if (isMatch) matches++;
    });

    list.style.display = matches > 0 ? 'grid' : 'none';
    noResults.hidden = matches > 0;
  }

  input.addEventListener('input', render);
  render(); // start hidden — no runner list on a fresh landing
})();
