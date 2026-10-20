// The feedback page: shows the details the app put in its link, and fills
// the form's hidden fields with them, so a person sees exactly what is sent.
// Only the names below are read (the app's own list: core/diagnostics.py,
// DETAIL_KEYS); anything else in the link is ignored. Text is set as text,
// never as markup.
(function () {
  "use strict";
  var LABELS = [
    ["version", "App version", ""],
    ["scale", "Screen scale", ""],
    ["sharp", "Sharp text", ""],
    ["theme", "Theme", ""],
    ["notes", "Notes", ""],
    ["files", "Attached files", ""],
    ["mb", "Notes file", " MB"],
    ["windows", "Windows", ""],
    ["build", "Runs as", ""]
  ];
  var RUNS_AS = { exe: "the installed app", source: "from source" };

  // The app puts its details after a "#", the part of a link the browser
  // keeps to itself, so they reach the site only with the form, when Send
  // is pressed. Older versions of the app put them in the query, read
  // here when the "#" holds none.
  function detailsInLink() {
    var hash = new URLSearchParams(window.location.hash.slice(1));
    var any = LABELS.some(function (entry) { return hash.has(entry[0]); });
    return any ? hash : new URLSearchParams(window.location.search);
  }

  function start() {
    var form = document.querySelector("form.feedback");
    var list = document.getElementById("details-list");
    var box = document.getElementById("details");
    if (!form || !list || !box) { return; }
    var params = detailsInLink();
    var shown = 0;
    LABELS.forEach(function (entry) {
      var key = entry[0];
      var value = (params.get(key) || "").slice(0, 80);
      if (!value) { return; }
      var field = form.querySelector('input[type="hidden"][name="' + key + '"]');
      if (field) { field.value = value; }
      var item = document.createElement("li");
      var shownValue = key === "build" ? (RUNS_AS[value] || value) : value;
      item.textContent = entry[1] + ": " + shownValue + entry[2];
      list.appendChild(item);
      shown += 1;
    });
    box.hidden = shown === 0;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
}());
