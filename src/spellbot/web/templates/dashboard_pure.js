/**
 * Pure (side-effect free) helpers for the admin dashboard.
 *
 * This file is concatenated with dashboard.js at serve time so top-level
 * function declarations become globals visible to the IIFE in dashboard.js.
 * The trailing `module.exports` block is a no-op in the browser and lets
 * Vitest import the same helpers under Node for unit testing.
 *
 * Helpers that previously used `Date.now()` directly now take the current
 * time as an argument so callers in dashboard.js pass `Date.now()` and tests
 * pass a fixed value.
 */

// Must mirror PERIOD_BUCKET / PERIOD_DAYS in dashboard_filters.py. Used
// client-side to compute bucket boundaries in UTC so leading/trailing
// partial buckets can be trimmed or dashed.
var PERIOD_BUCKET = {
  "7d": "day",
  "30d": "day",
  "90d": "day",
  "180d": "week",
  "365d": "week",
  "730d": "month",
  all: "month",
};
var PERIOD_DAYS = {
  "7d": 7,
  "30d": 30,
  "90d": 90,
  "180d": 180,
  "365d": 365,
  "730d": 730,
};

function currentBucket(period) {
  return PERIOD_BUCKET[period] || "day";
}

function periodStartMs(period, nowMs) {
  if (period === "all") return null;
  var days = PERIOD_DAYS[period];
  if (days == null) return null;
  return nowMs - days * 24 * 60 * 60 * 1000;
}

// Bucket dates come from Postgres `date_trunc` (UTC), so parse and add
// bucket sizes in UTC to keep the "is this bucket still in progress?" check
// accurate regardless of the browser's timezone.
function bucketStartUtc(iso) {
  return new Date(iso.slice(0, 10) + "T00:00:00Z");
}

function bucketEndUtc(start, bucket) {
  var d = new Date(start.getTime());
  if (bucket === "week") d.setUTCDate(d.getUTCDate() + 7);
  else if (bucket === "month") d.setUTCMonth(d.getUTCMonth() + 1);
  else d.setUTCDate(d.getUTCDate() + 1);
  return d;
}

// Given an array of ISO date strings (bucket starts) and the current bucket
// size, return the slice index of the first complete bucket and the index
// (within that slice) where trailing partial buckets begin. `startMs` is
// the inclusive lower bound of the visible window (or `null` for "all").
function computeTrim(rawDates, bucket, nowMs, startMs) {
  var startIdx = 0;
  if (startMs != null) {
    while (startIdx < rawDates.length) {
      var bs = bucketStartUtc(rawDates[startIdx]);
      if (bs.getTime() >= startMs) break;
      startIdx += 1;
    }
  }
  var partialFromIdx = rawDates.length - startIdx;
  for (var i = rawDates.length - 1; i >= startIdx; i -= 1) {
    var be = bucketEndUtc(bucketStartUtc(rawDates[i]), bucket);
    if (be.getTime() > nowMs) partialFromIdx = i - startIdx;
    else break;
  }
  return { startIdx: startIdx, partialFromIdx: partialFromIdx };
}

function unifyDates(seriesArray) {
  var all = new Set();
  seriesArray.forEach(function (series) {
    series.forEach(function (p) {
      all.add(p.date);
    });
  });
  return Array.from(all).sort();
}

function alignSeries(rawDates, series) {
  var map = {};
  series.forEach(function (p) {
    map[p.date] = p.count;
  });
  return rawDates.map(function (d) {
    return { date: d, count: map[d] || 0 };
  });
}

function guildParam(guildMode, guildXid) {
  if (guildMode === "all" || !guildXid) return "all";
  if (guildMode === "exclude") return "not:" + guildXid;
  return guildXid;
}

function qs(period, guildMode, guildXid) {
  return (
    "?period=" +
    encodeURIComponent(period) +
    "&guild=" +
    encodeURIComponent(guildParam(guildMode, guildXid))
  );
}

function fmt(n) {
  return n == null ? "—" : Number(n).toLocaleString();
}

function avgCount(series) {
  if (!series || !series.length) return 0;
  var total = 0;
  for (var i = 0; i < series.length; i += 1) total += series[i].count;
  return Math.round(total / series.length);
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

// Interpolates between `lo` (default deep indigo) and `hi` (default pink)
// on a square-root scale so light cells remain visible when the max value
// dwarfs the rest of the heatmap.
function heatColor(value, maxValue, lo, hi) {
  var loRGB = lo || [30, 58, 138];
  var hiRGB = hi || [244, 114, 182];
  if (!maxValue || !value) {
    return "rgb(" + loRGB[0] + "," + loRGB[1] + "," + loRGB[2] + ")";
  }
  var t = Math.sqrt(value / maxValue);
  var r = Math.round(loRGB[0] + (hiRGB[0] - loRGB[0]) * t);
  var g = Math.round(loRGB[1] + (hiRGB[1] - loRGB[1]) * t);
  var b = Math.round(loRGB[2] + (hiRGB[2] - loRGB[2]) * t);
  return "rgb(" + r + "," + g + "," + b + ")";
}

/* v8 ignore next */
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    PERIOD_BUCKET: PERIOD_BUCKET,
    PERIOD_DAYS: PERIOD_DAYS,
    currentBucket: currentBucket,
    periodStartMs: periodStartMs,
    bucketStartUtc: bucketStartUtc,
    bucketEndUtc: bucketEndUtc,
    computeTrim: computeTrim,
    unifyDates: unifyDates,
    alignSeries: alignSeries,
    guildParam: guildParam,
    qs: qs,
    fmt: fmt,
    avgCount: avgCount,
    escapeHtml: escapeHtml,
    heatColor: heatColor,
  };
}
