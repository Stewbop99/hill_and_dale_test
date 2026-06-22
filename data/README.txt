Data folder
===========

This folder holds the static data files that drive the site. Nothing here
is executed — runner-search.js fetches these as plain JSON at runtime.

runners.json
------------
An array of runner objects, used by index.html for the search/filter list
and by runner-search.js to build links to each runner's page.

[
  {
    "id": "jim-brown",            // matches runners/<id>.html
    "name": "Jim Brown",
    "school": "Hill and Dale High",
    "graduationYear": 2025,
    "events": ["5K", "8K"],
    "personalBests": {
      "5K": "16:32",
      "8K": "27:10"
    }
  }
]

races.json (future)
--------------------
Will hold race results per meet, keyed by race id, so head-to-head/index.html
can compute matchups without hardcoding times.

Until real data is supplied, runners.json contains a few sample entries so
the search UI has something to filter against.
