/**
 * Pure (side-effect free) helpers shared by the admin dashboard and the guild analytics page.
 *
 * This file is concatenated ahead of each page's own scripts at serve time, so its top-level
 * function declarations are globals for both pages. The trailing `module.exports` block is a
 * no-op in the browser and lets Vitest import the same helpers under Node.
 */

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, function (c) {
    return {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c];
  });
}

// Format a count with thousands separators, or an em dash when there is no value.
function fmt(n) {
  return n == null ? "—" : Number(n).toLocaleString();
}

function getTimezoneOffsetHours(date) {
  return -date.getTimezoneOffset() / 60;
}

// Convert UTC hour (0-23) to local hour. `offsetHours` is the result of
// `getTimezoneOffsetHours` so positive values are east of UTC.
function utcHourToLocal(utcHour, offsetHours) {
  var localHour = (utcHour + offsetHours) % 24;
  if (localHour < 0) localHour += 24;
  return Math.floor(localHour);
}

// Render `rows` as a table, or a "No data yet." note when there are none. Each column is
// `{header, cell, cls}`: `header` is plain text, `cell(row)` returns the cell's HTML (escape any
// text it shows), and `cls` is an optional cell class ("num" and "pct" right-align).
function renderTable(columns, rows) {
  if (!rows.length) return '<div class="no-data">No data yet.</div>';
  var head = columns
    .map(function (col) {
      var align = col.cls ? ' style="text-align:right"' : "";
      return "<th" + align + ">" + escapeHtml(col.header) + "</th>";
    })
    .join("");
  var body = rows
    .map(function (row) {
      var cells = columns
        .map(function (col) {
          var cls = col.cls ? ' class="' + col.cls + '"' : "";
          return "<td" + cls + ">" + col.cell(row) + "</td>";
        })
        .join("");
      return "<tr>" + cells + "</tr>";
    })
    .join("");
  return (
    '<table class="lang-table"><thead><tr>' +
    head +
    "</tr></thead><tbody>" +
    body +
    "</tbody></table>"
  );
}

var CLOUD_COLORS = [
  "#a78bfa", // purple
  "#60a5fa", // blue
  "#4ade80", // green
  "#f472b6", // pink
  "#fbbf24", // amber
  "#67e8f9", // cyan
  "#fb923c", // orange
  "#a3e635", // lime
];

// Render `{phrase, count}` n-grams as a word cloud. Sizes and opacity follow a log scale of the
// counts, so a few very common phrases don't dwarf the rest. `random` (Math.random in the
// browser) shuffles the order and tilts each word slightly, for a more organic look.
function wordCloudHtml(ngrams, random) {
  var counts = ngrams.map(function (n) {
    return n.count;
  });
  var logMin = Math.log(Math.min.apply(null, counts) || 1);
  var logRange = Math.log(Math.max.apply(null, counts) || 1) - logMin || 1;
  var words = ngrams
    .slice()
    .sort(function () {
      return random() - 0.5;
    })
    .map(function (n, i) {
      var scale = (Math.log(n.count || 1) - logMin) / logRange;
      return (
        '<span class="cloud-word" style="font-size:' +
        (0.8 + scale * 1.2) +
        "rem;color:" +
        CLOUD_COLORS[i % CLOUD_COLORS.length] +
        ";opacity:" +
        (0.75 + scale * 0.25) +
        ";transform:rotate(" +
        (random() - 0.5) * 8 +
        'deg)" title="' +
        n.count +
        ' games">' +
        escapeHtml(n.phrase) +
        "</span>"
      );
    })
    .join("");
  return '<div class="word-cloud">' + words + "</div>";
}

/* v8 ignore next */
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    escapeHtml: escapeHtml,
    fmt: fmt,
    getTimezoneOffsetHours: getTimezoneOffsetHours,
    utcHourToLocal: utcHourToLocal,
    renderTable: renderTable,
    wordCloudHtml: wordCloudHtml,
  };
}
