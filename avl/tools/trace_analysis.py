#!/usr/bin/env python3

import argparse
import html
import json
import sys

import pandas as pd
import tabulate

from avl.tools.coverage_analysis import logo

REPORT_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>__TITLE__</title>
<style>
:root {
  --navy: #0b2c52;
  --navy-2: #123a6b;
  --blue: #4a82c4;
  --blue-light: #cfe3ff;
  --blue-pale: #eef4fc;
  --grey: #838383;
  --grey-dark: #45505c;
  --bg: #eef1f5;
  --panel: #ffffff;
  --border: #dde3ea;
  --text: #26313d;
}

* { box-sizing: border-box; }

html, body {
  height: 100%;
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: var(--text);
  background: var(--bg);
}

body { display: flex; flex-direction: column; }

.app-header {
  flex: 0 0 auto;
  height: 60px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0 1.25rem;
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  box-shadow: 0 1px 4px rgba(20, 30, 50, 0.06);
}
.app-header img { height: 34px; width: auto; display: block; }
.app-header h1 {
  font-size: 1.05rem;
  font-weight: 600;
  margin: 0;
  color: var(--navy);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.content { flex: 1; min-height: 0; display: flex; flex-direction: column; padding: 1rem 1.25rem; }

.panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.panel-header {
  flex: 0 0 auto;
  padding: 0.6rem 1.1rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
}
.panel-header h2 { font-size: 0.95rem; margin: 0; color: var(--navy); }
.panel-header .panel-subtitle { font-size: 0.8rem; color: var(--grey); }

.grid-host { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.grid-toolbar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.6rem 1.1rem;
}
.grid-search {
  flex: 0 0 260px;
  padding: 0.4rem 0.65rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.85rem;
  outline: none;
}
.grid-search:focus { border-color: var(--blue); box-shadow: 0 0 0 2px var(--blue-pale); }
.grid-count { font-size: 0.8rem; color: var(--grey); white-space: nowrap; }

.grid-scroll { flex: 1; min-height: 0; overflow: auto; padding: 0 1.1rem; }

table { width: 100%; border-collapse: collapse; font-size: 0.82rem; font-variant-numeric: tabular-nums; }
thead th {
  position: sticky;
  top: 0;
  background: var(--blue-pale);
  color: var(--navy);
  text-align: left;
  padding: 0.5rem 0.6rem;
  font-weight: 600;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
  z-index: 1;
}
thead th.sortable { cursor: pointer; }
thead th.sortable:hover { background: var(--blue-light); }
thead th.num, tbody td.num { text-align: right; }
tr.filter-row th {
  padding: 0.3rem 0.4rem;
  background: var(--panel);
  top: 32px;
}
tr.filter-row input {
  width: 100%;
  padding: 0.28rem 0.4rem;
  font-size: 0.78rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  outline: none;
}
tr.filter-row input:focus { border-color: var(--blue); }
tbody td { padding: 0.42rem 0.6rem; border-bottom: 1px solid var(--border); vertical-align: middle; }
tbody tr:nth-child(even) { background: rgba(74, 130, 196, 0.03); }
tbody tr.empty-row td { color: var(--grey); text-align: center; padding: 1.2rem; }

.grid-pagination {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.6rem;
  padding: 0.5rem 1.1rem;
  font-size: 0.8rem;
  color: var(--grey-dark);
}
.grid-pagination button {
  border: 1px solid var(--border);
  background: var(--panel);
  border-radius: 5px;
  padding: 0.25rem 0.7rem;
  font-size: 0.8rem;
  cursor: pointer;
}
.grid-pagination button:disabled { opacity: 0.4; cursor: default; }
.grid-pagination button:not(:disabled):hover { background: var(--blue-pale); }

input:focus-visible, button:focus-visible { outline: 2px solid var(--blue); outline-offset: 1px; }
</style>
</head>
<body>
  <header class="app-header">
    __LOGO__
    <h1>__TITLE__</h1>
  </header>
  <div class="content">
    <section class="panel">
      <div class="panel-header">
        <h2>Trace Data</h2>
        <span class="panel-subtitle" id="panel-subtitle"></span>
      </div>
      <div class="grid-host" id="trace-grid"></div>
    </section>
  </div>

<script>
const COLUMNS = __COLUMNS_JSON__;
const ROWS = __ROWS_JSON__;

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

function tryNumber(s) {
  if (s === null || s === undefined) return NaN;
  s = String(s).replace(/[,\s%]/g, "").trim();
  if (s === "") return NaN;
  var n = Number(s);
  return Number.isNaN(n) ? NaN : n;
}

function matchFilter(cellText, filterRaw) {
  var val = filterRaw.trim();
  if (!val) return true;
  var cell = String(cellText);
  var m = val.match(/^([<>]=?|!=|=|\^=|\$=|~=)\s*(.*)$/);
  if (m) {
    var op = m[1], rhs = m[2].trim();
    if (op === "=") return cell === rhs;
    if (op === "!=") return cell !== rhs;
    if (op === "^=") return cell.toLowerCase().indexOf(rhs.toLowerCase()) === 0;
    if (op === "$=") return cell.toLowerCase().slice(-rhs.length) === rhs.toLowerCase();
    if (op === "~=") {
      try { return new RegExp(rhs, "i").test(cell); } catch (e) { return false; }
    }
    var lhsNum = tryNumber(cell), rhsNum = tryNumber(rhs);
    if (Number.isNaN(lhsNum) || Number.isNaN(rhsNum)) return false;
    if (op === ">") return lhsNum > rhsNum;
    if (op === ">=") return lhsNum >= rhsNum;
    if (op === "<") return lhsNum < rhsNum;
    if (op === "<=") return lhsNum <= rhsNum;
  }
  return cell.toLowerCase().indexOf(val.toLowerCase()) !== -1;
}

/* Sortable / filterable / searchable table, paginated client-side. */
class Grid {
  constructor(container, columns, rows, opts) {
    this.container = container;
    this.columns = columns;
    this.rows = rows || [];
    this.opts = opts || {};
    this.sortKey = this.opts.defaultSortKey || null;
    this.sortDir = this.opts.defaultSortDir || 1;
    this.filters = {};
    this.search = "";
    this.page = 0;
    this.pageSize = this.opts.pageSize || 25;
    this.render();
  }

  process() {
    var rows = this.rows;
    var self = this;

    if (this.search) {
      var q = this.search.toLowerCase();
      rows = rows.filter(function (r) {
        return self.columns.some(function (c) {
          return String(r[c.key] === undefined || r[c.key] === null ? "" : r[c.key]).toLowerCase().indexOf(q) !== -1;
        });
      });
    }

    Object.keys(this.filters).forEach(function (key) {
      var f = self.filters[key];
      if (!f) return;
      rows = rows.filter(function (r) {
        return matchFilter(r[key] === undefined || r[key] === null ? "" : r[key], f);
      });
    });

    if (this.sortKey) {
      var col = this.columns.find(function (c) { return c.key === self.sortKey; });
      var dir = this.sortDir;
      rows = rows.slice().sort(function (a, b) {
        var av = a[self.sortKey], bv = b[self.sortKey];
        if (col && col.type === "number") {
          av = Number(av); bv = Number(bv);
          if (Number.isNaN(av)) av = -Infinity;
          if (Number.isNaN(bv)) bv = -Infinity;
          return (av - bv) * dir;
        }
        av = String(av === undefined || av === null ? "" : av);
        bv = String(bv === undefined || bv === null ? "" : bv);
        return av.localeCompare(bv, undefined, { numeric: true, sensitivity: "base" }) * dir;
      });
    }
    return rows;
  }

  render() {
    var self = this;
    var active = document.activeElement;
    var restore = null;
    if (active && this.container.contains(active) && active.tagName === "INPUT") {
      restore = {
        isSearch: active.classList.contains("grid-search"),
        key: active.dataset ? active.dataset.key : null,
        start: active.selectionStart,
        end: active.selectionEnd,
      };
    }

    var rows = this.process();
    var total = rows.length;
    var maxPage = Math.max(0, Math.ceil(total / this.pageSize) - 1);
    if (this.page > maxPage) this.page = maxPage;
    var start = this.page * this.pageSize;
    var pageRows = rows.slice(start, start + this.pageSize);

    var html = "";
    html += '<div class="grid-toolbar">';
    html += '<input type="search" class="grid-search" placeholder="Search all columns..." value="' + escapeHtml(this.search) + '">';
    html += '<span class="grid-count">' + (total === 0 ? "No rows" :
      (start + 1) + "–" + Math.min(start + pageRows.length, total) + " of " + total) + "</span>";
    html += "</div>";

    html += '<div class="grid-scroll"><table><thead><tr>';
    this.columns.forEach(function (col) {
      var arrow = self.sortKey === col.key ? (self.sortDir === 1 ? " ▲" : " ▼") : "";
      var numCls = col.align === "right" ? " num" : "";
      html += '<th data-key="' + col.key + '" class="sortable' + numCls + '">' + escapeHtml(col.label) + arrow + "</th>";
    });
    html += '</tr><tr class="filter-row">';
    this.columns.forEach(function (col) {
      var v = self.filters[col.key] || "";
      html += '<th><input type="text" data-key="' + col.key + '" placeholder="Filter" title="=, !=, >, >=, <, <=, ^=, $=, ~=" value="' + escapeHtml(v) + '"></th>';
    });
    html += "</tr></thead><tbody>";

    if (pageRows.length === 0) {
      html += '<tr class="empty-row"><td colspan="' + this.columns.length + '">No matching rows</td></tr>';
    }
    pageRows.forEach(function (row) {
      html += "<tr>";
      self.columns.forEach(function (col) {
        var v = row[col.key];
        var content = escapeHtml(v === undefined || v === null ? "" : v);
        var numCls = col.align === "right" ? ' class="num"' : "";
        html += "<td" + numCls + ">" + content + "</td>";
      });
      html += "</tr>";
    });
    html += "</tbody></table></div>";

    if (total > this.pageSize) {
      var pages = Math.ceil(total / this.pageSize);
      html += '<div class="grid-pagination">';
      html += '<button data-act="prev"' + (this.page <= 0 ? " disabled" : "") + ">Prev</button>";
      html += "<span>Page " + (this.page + 1) + " of " + pages + "</span>";
      html += '<button data-act="next"' + (this.page >= pages - 1 ? " disabled" : "") + ">Next</button>";
      html += "</div>";
    }

    this.container.innerHTML = html;
    this.attach();

    if (restore) {
      var el = restore.isSearch
        ? this.container.querySelector(".grid-search")
        : this.container.querySelector('.filter-row input[data-key="' + restore.key + '"]');
      if (el) {
        el.focus();
        try { el.setSelectionRange(restore.start, restore.end); } catch (e) { /* ignore */ }
      }
    }
  }

  attach() {
    var self = this;
    var c = this.container;

    var searchEl = c.querySelector(".grid-search");
    searchEl.addEventListener("input", function () {
      self.search = searchEl.value;
      self.page = 0;
      self.render();
    });

    c.querySelectorAll(".filter-row input").forEach(function (inp) {
      inp.addEventListener("input", function () {
        self.filters[inp.dataset.key] = inp.value;
        self.page = 0;
        self.render();
      });
    });

    c.querySelector("thead").addEventListener("click", function (e) {
      var th = e.target.closest("th[data-key]");
      if (!th) return;
      var key = th.dataset.key;
      if (self.sortKey === key) self.sortDir *= -1;
      else { self.sortKey = key; self.sortDir = 1; }
      self.render();
    });

    var pag = c.querySelector(".grid-pagination");
    if (pag) {
      pag.addEventListener("click", function (e) {
        var btn = e.target.closest("button[data-act]");
        if (!btn) return;
        if (btn.dataset.act === "prev" && self.page > 0) self.page--;
        if (btn.dataset.act === "next") self.page++;
        self.render();
      });
    }
  }
}

document.getElementById("panel-subtitle").textContent = ROWS.length + " rows × " + COLUMNS.length + " columns";
new Grid(document.getElementById("trace-grid"), COLUMNS, ROWS, {});
</script>
</body>
</html>
"""


def _column_defs(df):
    """Build {key, label, type, align} column metadata for the embedded grid, one per DataFrame column."""
    columns = []
    for col in df.columns:
        numeric = pd.api.types.is_numeric_dtype(df[col])
        columns.append({
            "key": col,
            "label": col,
            "type": "number" if numeric else "string",
            "align": "right" if numeric else "left",
        })
    return columns


def _parse_sort(sort_arg):
    """Split a --sort value into (column, ascending), honoring an optional leading '-' for descending order."""
    if sort_arg.startswith("-"):
        return sort_arg[1:], False
    return sort_arg, True


def main():
    parser = argparse.ArgumentParser(description="Analyze and visualize AVL trace data")
    parser.add_argument("--tracefile", nargs="+", required=True, type=str, help="Trace file(s) to analyze.")
    parser.add_argument("--query", type=str, help="Query to filter trace data.", default=None)
    parser.add_argument(
        "--sort", type=str, default=None,
        help="Column to sort by. Prefix with '-' for descending (use --sort=-col so it isn't parsed as a flag).",
    )
    parser.add_argument("--output", type=str, help="Output HTML file name.", default=None)
    parser.add_argument("--debug", action="store_true", help="Enable debug mode for detailed output.")

    args = parser.parse_args()

    try:
        df = pd.concat([pd.read_csv(f) for f in args.tracefile], ignore_index=True)
    except OSError as e:
        sys.exit(f"error: could not read trace file: {e}")
    except pd.errors.EmptyDataError as e:
        sys.exit(f"error: trace file has no data: {e}")

    # Run Query if provided
    if args.query:
        if args.debug:
            print(f"Applying query: {args.query}")
        try:
            df = df.query(args.query)
        except Exception as e:
            sys.exit(f"error: invalid --query {args.query!r}: {e}\nAvailable columns: {', '.join(df.columns)}")

    # Sort by column if specified
    if args.sort:
        column, ascending = _parse_sort(args.sort)
        if column not in df.columns:
            sys.exit(f"error: unknown --sort column {column!r}\nAvailable columns: {', '.join(df.columns)}")
        if args.debug:
            direction = "ascending" if ascending else "descending"
            print(f"Sorting by column: {column} ({direction})")
        df = df.sort_values(by=column, ascending=ascending)

    # Output to HTML if specified
    if args.output:
        if args.debug:
            print(f"Writing output to: {args.output}")

        title = html.escape(args.query or "AVL Trace Analysis")
        rows_json = df.to_json(orient="records").replace("</", "<\\/")
        columns_json = json.dumps(_column_defs(df))
        html_content = (
            REPORT_TEMPLATE
            .replace("__LOGO__", logo)
            .replace("__TITLE__", title)
            .replace("__COLUMNS_JSON__", columns_json)
            .replace("__ROWS_JSON__", rows_json)
        )

        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(html_content)
        except OSError as e:
            sys.exit(f"error: could not write output file: {e}")
    else:
        print(tabulate.tabulate(df.values.tolist(), headers=df.columns, tablefmt="grid"))


if __name__ == "__main__":
    main()
