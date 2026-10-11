/**
 * FLWU Public Search.
 * Exports filterRows(rows, filters) for deterministic filtering.
 * Attaches event handlers after DOMContentLoaded.
 */
(function() {
  "use strict";

  /** Filter inventory rows by applied filters (AND semantics). */
  function filterRows(rows, filters) {
    return rows.filter(function(row) {
      return Object.keys(filters).every(function(key) {
        var value = filters[key];
        if (!value || value.trim() === "") return true;

        if (key === "query") {
          var q = value.toLowerCase();
          return (row.title || "").toLowerCase().indexOf(q) !== -1 ||
                 (row.text || "").toLowerCase().indexOf(q) !== -1;
        }

        if (["county", "circuit", "court_level", "division", "topic"].indexOf(key) !== -1) {
          var list = row[key] || [];
          return list.indexOf(value) !== -1;
        }

        return true;
      });
    });
  }

  window.filterRows = filterRows;

  function attachHandlers() {
    var submitBtn = document.getElementById("search-submit");
    if (!submitBtn) return;

    submitBtn.addEventListener("click", function() {
      var filters = {
        query: document.getElementById("query") ? document.getElementById("query").value : "",
        county: document.getElementById("county") ? document.getElementById("county").value : "",
        circuit: document.getElementById("circuit") ? document.getElementById("circuit").value : "",
        topic: document.getElementById("topic") ? document.getElementById("topic").value : "",
      };

      var results = filterRows(window._inventoryRows || [], filters);

      var resultsDiv = document.getElementById("results");
      if (resultsDiv) {
        resultsDiv.innerHTML = results.map(function(r) {
          return '<article class="result" data-record-id="' + r.record_id + '">' +
                 '<h3>' + escapeHtml(r.title) + '</h3>' +
                 '<p>' + escapeHtml(r.text || "") + '</p></article>';
        }).join("");
      }

      var statusDiv = document.getElementById("search-status");
      if (statusDiv) {
        statusDiv.textContent = results.length + " result" + (results.length !== 1 ? "s" : "") + " found.";
      }
    });
  }

  function escapeHtml(text) {
    if (!text) return "";
    return text.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }

  if (typeof document !== "undefined" && document.addEventListener) {
    document.addEventListener("DOMContentLoaded", attachHandlers);
  }
})();
