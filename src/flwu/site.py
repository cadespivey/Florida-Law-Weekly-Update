"""Static site generation (C36).

Generates HTML, CSS, and JS for the public website.
Produces public/index.html, public/procedures/index.html,
public/assets/site.css, and public/assets/search.js.
"""
from __future__ import annotations
from typing import Any
from pathlib import Path

def generate_site(issue, inventory_rows, output_dir):
    """Generate the full static site."""
    (output_dir / "public").mkdir(parents=True, exist_ok=True)
    (output_dir / "public" / "assets").mkdir(parents=True, exist_ok=True)

    # index.html
    (output_dir / "public" / "index.html").write_text(_generate_index(issue), encoding="utf-8")

    # procedures/index.html
    (output_dir / "public" / "procedures").mkdir(parents=True, exist_ok=True)
    (output_dir / "public" / "procedures" / "index.html").write_text(
        _generate_procedures_page(inventory_rows), encoding="utf-8")

    # Static assets
    (output_dir / "public" / "assets" / "site.css").write_text(_site_css(), encoding="utf-8")
    (output_dir / "public" / "assets" / "search.js").write_text(_search_js(), encoding="utf-8")

    return output_dir / "public"


def _generate_index(issue):
    title = _esc(issue.get("title", "FLWU"))
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>{title} — FLWU</title>
<link rel="stylesheet" href="assets/site.css">
</head><body><h1>{title}</h1>
<p><a href="procedures/">Search Procedures</a></p>
<footer>Florida Litigator Weekly Update — nonofficial informational publication.</footer>
</body></html>"""


def _generate_procedures_page(rows):
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>FLWU Search</title>
<link rel="stylesheet" href="assets/site.css">
</head><body>
<h1 id="search-header">Search Procedures</h1>
<form id="search-form">
<label for="query">Query:</label><input id="query" type="text">
<label for="county">County:</label><input id="county" type="text">
<label for="circuit">Circuit:</label><input id="circuit" type="text">
<label for="topic">Topic:</label><input id="topic" type="text">
<button id="search-submit" type="button">Search</button>
<div id="search-status" role="status" aria-live="polite"></div>
<div id="results"></div>
</form>
<script src="assets/search.js"></script>
<footer>FLWU public site. Not a substitute for legal advice.</footer>
</body></html>"""


def _site_css():
    return """body{font-family:system-ui,sans-serif;max-width:800px;margin:2em auto;}
h1{color:#222}#search-form{margin:1em 0}#results{margin:1em 0}
.result{border:1px solid #ddd;padding:0.5em;margin:0.5em 0}
footer{font-size:0.85em;color:#666}"""


def _search_js():
    return """(function(){
  function filterRows(rows,filters){
    return rows.filter(function(r){
      return Object.keys(filters).every(function(k){
        var v=filters[k];
        if(!v)return true;
        if(k==='query'){
          var ql=v.toLowerCase();
          return r.title.toLowerCase().indexOf(ql)!==-1||r.text.toLowerCase().indexOf(ql)!==-1;
        }
        if(k==='county'||k==='circuit'||k==='court_level'||k==='division'||k==='topic')
          return (r[k]||[]).indexOf(v)!==-1;
        return true;
      });
    });
  }
  document.getElementById('search-submit').addEventListener('click',function(){
    var filters={
      query:document.getElementById('query').value,
      county:document.getElementById('county').value,
      circuit:document.getElementById('circuit').value,
      topic:document.getElementById('topic').value,
    };
    var results=filterRows(window._inventoryRows||[],filters);
    var div=document.getElementById('results');
    div.innerHTML=results.map(function(r){
      return '<article class="result" data-record-id="'+r.record_id+'"><h3>'+r.title+'</h3>';
    }).join('');
  });
})();"""


def _esc(text):
    if not isinstance(text, str):
        text = str(text)
    return text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
