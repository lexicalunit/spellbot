/**
 * Pure (side-effect free) helpers for the analytics page.
 *
 * Concatenated with analytics.js at serve time so top-level declarations
 * become globals visible to the IIFE in analytics.js. The trailing
 * `module.exports` block is a no-op in the browser and lets Vitest import
 * the same helpers under Node for unit testing.
 *
 * Time-dependent helpers take the current date as an argument so callers in
 * analytics.js pass `new Date()` and tests pass a fixed instant.
 */

function toDayMap(arr) {
  var m = {};
  arr.forEach(function (d) {
    m[d.day] = d.count;
  });
  return m;
}

function fmt(n) {
  return n.toLocaleString();
}

function periodLabel(period) {
  return period === "all" ? "All Time" : "Last 30 Days";
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

// Today in YYYY-MM-DD (UTC).
function getTodayUTC(date) {
  return date.toISOString().split("T")[0];
}

// Today in YYYY-MM-DD (the date's local timezone).
function getTodayLocal(date) {
  var year = date.getFullYear();
  var month = String(date.getMonth() + 1).padStart(2, "0");
  var day = String(date.getDate()).padStart(2, "0");
  return year + "-" + month + "-" + day;
}

// Filter out the current (incomplete) day from a sorted list of YYYY-MM-DD
// strings. Excludes both UTC and local-today to handle every browser tz.
function excludeToday(days, date) {
  var todayUTC = getTodayUTC(date);
  var todayLocal = getTodayLocal(date);
  return days.filter(function (d) {
    return d !== todayUTC && d !== todayLocal;
  });
}

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

function renderPlayerRow(p) {
  var leftBadge = p.left_server
    ? '<span class="left-badge" title="User has left the server and will be removed on next refresh">left</span>'
    : "";
  var rowClass = p.left_server ? ' class="left-server"' : "";
  return (
    "<tr" +
    rowClass +
    "><td>" +
    escapeHtml(p.name) +
    leftBadge +
    '</td><td style="color:#9ca3af;font-size:0.8rem">' +
    p.user_xid +
    '</td><td class="count">' +
    fmt(p.count) +
    "</td></tr>"
  );
}

function renderLeftServerNote(players) {
  var hasLeftServer = players.some(function (p) {
    return p.left_server;
  });
  if (!hasLeftServer) return "";
  return '<div class="left-server-note"><span class="left-badge">left</span> = User has left the server. They will not appear on the next page load.</div>';
}

// Returns the user's timezone abbreviation (e.g. `PST`) or, as a fallback,
// a `UTC±N` string derived from the date's offset. `date` lets tests pin
// the moment; the abbreviation still depends on the runtime's locale data.
function getUserTimezone(date) {
  try {
    var formatter = new Intl.DateTimeFormat("en-US", {
      timeZoneName: "short",
    });
    var parts = formatter.formatToParts(date);
    var tzPart = parts.find(function (p) {
      return p.type === "timeZoneName";
    });
    if (tzPart) return tzPart.value;
  } catch (_e) {
    /* fall through to UTC offset */
  }
  var offset = getTimezoneOffsetHours(date);
  var sign = offset >= 0 ? "+" : "";
  return "UTC" + sign + offset;
}

// Looks up a human-readable language name for the given BCP 47 `locale`.
// `displayNames` is an injected `Intl.DisplayNames` instance so callers
// can reuse a singleton (and tests can stub it).
function getLanguageName(locale, displayNames) {
  try {
    return displayNames.of(locale) || locale;
  } catch (_e) {
    return locale;
  }
}

/* v8 ignore next */
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    toDayMap: toDayMap,
    fmt: fmt,
    periodLabel: periodLabel,
    getTimezoneOffsetHours: getTimezoneOffsetHours,
    utcHourToLocal: utcHourToLocal,
    getTodayUTC: getTodayUTC,
    getTodayLocal: getTodayLocal,
    excludeToday: excludeToday,
    escapeHtml: escapeHtml,
    renderPlayerRow: renderPlayerRow,
    renderLeftServerNote: renderLeftServerNote,
    getUserTimezone: getUserTimezone,
    getLanguageName: getLanguageName,
  };
}
