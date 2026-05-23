/**
 * SpellBot Admin Dashboard.
 *
 * Talks to /admin/dashboard/* endpoints. Reads "period" and "guild" filters
 * from the controls in dashboard.html.j2 and re-renders all panels on change.
 */
(function () {
  "use strict";

  if (!window.CHART_AVAILABLE) {
    document.querySelectorAll(".chart-box").forEach(function (el) {
      el.innerHTML =
        '<div class="section-error">Charts unavailable. Check your connection and refresh.</div>';
    });
    return;
  }

  const GRID = "rgba(255,255,255,0.08)";
  const TICK = "#9ca3af";
  Chart.defaults.color = TICK;
  Chart.defaults.borderColor = GRID;

  // Saturated, high-contrast palette of 20 colors that spans the spectrum.
  // Ordered so adjacent series in the stack/legend are maximally distinct.
  const COLORS = [
    "#ef4444", // red
    "#3b82f6", // blue
    "#facc15", // yellow
    "#a855f7", // purple
    "#22c55e", // green
    "#ec4899", // pink
    "#f97316", // orange
    "#06b6d4", // cyan
    "#84cc16", // lime
    "#6366f1", // indigo
    "#dc2626", // dark red
    "#0ea5e9", // sky
    "#eab308", // gold
    "#7c3aed", // deep purple
    "#16a34a", // forest green
    "#db2777", // magenta
    "#ea580c", // burnt orange
    "#0d9488", // teal
    "#65a30d", // olive
    "#4338ca", // deep indigo
  ];

  const state = {
    period: "30d",
    guildMode: "all",
    guildXid: "",
    charts: {},
  };

  // Must mirror PERIOD_BUCKET / PERIOD_DAYS in dashboard_filters.py. Used
  // client-side to compute bucket boundaries in the browser's local timezone
  // so leading/trailing partial buckets can be trimmed or dashed.
  const PERIOD_BUCKET = {
    "7d": "day",
    "30d": "day",
    "90d": "day",
    "180d": "week",
    "365d": "week",
    "730d": "month",
    all: "month",
  };
  const PERIOD_DAYS = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "180d": 180,
    "365d": 365,
    "730d": 730,
  };

  function currentBucket() {
    return PERIOD_BUCKET[state.period] || "day";
  }

  function periodStartMs() {
    if (state.period === "all") return null;
    const days = PERIOD_DAYS[state.period];
    if (days == null) return null;
    return Date.now() - days * 24 * 60 * 60 * 1000;
  }

  // Bucket dates come from Postgres ``date_trunc`` (UTC), so parse and add
  // bucket sizes in UTC to keep the "is this bucket still in progress?" check
  // accurate regardless of the browser's timezone.
  function bucketStartUtc(iso) {
    return new Date(iso.slice(0, 10) + "T00:00:00Z");
  }

  function bucketEndUtc(start, bucket) {
    const d = new Date(start.getTime());
    if (bucket === "week") d.setUTCDate(d.getUTCDate() + 7);
    else if (bucket === "month") d.setUTCMonth(d.getUTCMonth() + 1);
    else d.setUTCDate(d.getUTCDate() + 1);
    return d;
  }

  // Given an array of ISO date strings (bucket starts) and the current bucket
  // size, return the slice index of the first complete bucket and the index
  // (within that slice) where trailing partial buckets begin.
  function computeTrim(rawDates, bucket) {
    const nowMs = Date.now();
    const startMs = periodStartMs();
    let startIdx = 0;
    if (startMs != null) {
      while (startIdx < rawDates.length) {
        const bs = bucketStartUtc(rawDates[startIdx]);
        if (bs.getTime() >= startMs) break;
        startIdx += 1;
      }
    }
    let partialFromIdx = rawDates.length - startIdx;
    for (let i = rawDates.length - 1; i >= startIdx; i -= 1) {
      const be = bucketEndUtc(bucketStartUtc(rawDates[i]), bucket);
      if (be.getTime() > nowMs) partialFromIdx = i - startIdx;
      else break;
    }
    return { startIdx: startIdx, partialFromIdx: partialFromIdx };
  }

  function dashSegment(partialFromIdx) {
    return {
      borderDash: function (ctx) {
        return ctx.p1DataIndex >= partialFromIdx ? [6, 4] : undefined;
      },
    };
  }

  function unifyDates(seriesArray) {
    const all = new Set();
    seriesArray.forEach(function (series) {
      series.forEach(function (p) {
        all.add(p.date);
      });
    });
    return Array.from(all).sort();
  }

  function alignSeries(rawDates, series) {
    const map = {};
    series.forEach(function (p) {
      map[p.date] = p.count;
    });
    return rawDates.map(function (d) {
      return { date: d, count: map[d] || 0 };
    });
  }

  function guildParam() {
    if (state.guildMode === "all" || !state.guildXid) return "all";
    if (state.guildMode === "exclude") return "not:" + state.guildXid;
    return state.guildXid;
  }

  function qs() {
    return (
      "?period=" +
      encodeURIComponent(state.period) +
      "&guild=" +
      encodeURIComponent(guildParam())
    );
  }

  async function fetchJson(path) {
    const res = await fetch("/admin/dashboard/" + path + qs(), {
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  function fmt(n) {
    return n == null ? "—" : Number(n).toLocaleString();
  }

  function showError(sectionId, msg) {
    document.getElementById(sectionId).innerHTML =
      '<div class="section-error">' + msg + "</div>";
  }
  function addCanvas(sectionId) {
    const el = document.getElementById(sectionId);
    el.innerHTML = "<canvas></canvas>";
    return el.querySelector("canvas");
  }
  function destroyChart(key) {
    if (state.charts[key]) {
      state.charts[key].destroy();
      delete state.charts[key];
    }
  }

  function lineOpts(stacked) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: true, labels: { color: "#e0e0e0", boxWidth: 12 } },
      },
      scales: {
        x: {
          stacked: !!stacked,
          grid: { color: GRID },
          ticks: { color: TICK, maxRotation: 45 },
        },
        y: {
          stacked: !!stacked,
          grid: { color: GRID },
          ticks: { color: TICK },
          beginAtZero: true,
        },
      },
    };
  }

  function lineDataset(label, points, color, fill) {
    return {
      label: label,
      data: points.map(function (p) {
        return p.count;
      }),
      borderColor: color,
      backgroundColor: color + "CC",
      borderWidth: 2,
      tension: 0,
      fill: !!fill,
      pointRadius: 0,
    };
  }

  const BRACKET_STAT_IDS = {
    BRACKET_1: "statBracket1",
    BRACKET_2: "statBracket2",
    BRACKET_3: "statBracket3",
    BRACKET_4: "statBracket4",
    BRACKET_5: "statBracket5",
  };

  function setBracketStats(brackets) {
    Object.keys(BRACKET_STAT_IDS).forEach(function (key) {
      const el = document.getElementById(BRACKET_STAT_IDS[key]);
      const value = brackets ? brackets[key] : null;
      if (value == null) {
        el.textContent = "—";
        return;
      }
      el.innerHTML =
        escapeHtml(fmt(value)) + ' <span class="stat-unit">games</span>';
    });
  }

  async function loadSummary() {
    try {
      const data = await fetchJson("summary");
      document.getElementById("statGames").textContent = fmt(data.games);
      document.getElementById("statPlayers").textContent = fmt(data.players);
      document.getElementById("statServers").textContent = fmt(data.servers);
      document.getElementById("bucketLabel").textContent = data.bucket || "—";
      setBracketStats(data.brackets);
    } catch (ex) {
      ["statGames", "statPlayers", "statServers"].forEach(function (id) {
        document.getElementById(id).textContent = "—";
      });
      document.getElementById("bucketLabel").textContent = "—";
      setBracketStats(null);
    }
  }

  async function loadTotals() {
    try {
      const data = await fetchJson("totals");
      document.getElementById("statTotalGames").textContent = fmt(data.games);
      document.getElementById("statTotalPlayers").textContent = fmt(
        data.players,
      );
      document.getElementById("statTotalServers").textContent = fmt(
        data.servers,
      );
    } catch (ex) {
      ["statTotalGames", "statTotalPlayers", "statTotalServers"].forEach(
        function (id) {
          document.getElementById(id).textContent = "—";
        },
      );
    }
  }

  function avgCount(series) {
    if (!series || !series.length) return 0;
    let total = 0;
    for (let i = 0; i < series.length; i += 1) total += series[i].count;
    return Math.round(total / series.length);
  }

  function applyDash(dataset, dash) {
    dataset.segment = dash;
    return dataset;
  }

  async function loadUsersActivity() {
    try {
      const d = await fetchJson("users-activity");
      document.getElementById("statDauMau").textContent =
        (d.dau_mau || 0) + "%";
      document.getElementById("statWau").textContent = fmt(avgCount(d.wau));
      document.getElementById("statMau").textContent = fmt(avgCount(d.mau));
      const rawDates = unifyDates([d.new_users, d.dau]);
      const trim = computeTrim(rawDates, currentBucket());
      const labels = rawDates.slice(trim.startIdx).map(function (s) {
        return s.slice(0, 10);
      });
      const newUsers = alignSeries(rawDates, d.new_users).slice(trim.startIdx);
      const dau = alignSeries(rawDates, d.dau).slice(trim.startIdx);
      const dash = dashSegment(trim.partialFromIdx);
      const ctx = addCanvas("usersActivitySection");
      destroyChart("usersActivity");
      state.charts.usersActivity = new Chart(ctx, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            applyDash(lineDataset("New Users", newUsers, COLORS[3]), dash),
            applyDash(lineDataset("Active Users", dau, COLORS[0]), dash),
          ],
        },
        options: lineOpts(false),
      });
    } catch (ex) {
      showError("usersActivitySection", "Failed to load user activity.");
      ["statWau", "statMau", "statDauMau"].forEach(function (id) {
        document.getElementById(id).textContent = "—";
      });
    }
  }

  async function loadGames() {
    try {
      const d = await fetchJson("games");
      const rawDates = unifyDates([d.started, d.expired]);
      const trim = computeTrim(rawDates, currentBucket());
      const labels = rawDates.slice(trim.startIdx).map(function (s) {
        return s.slice(0, 10);
      });
      const started = alignSeries(rawDates, d.started).slice(trim.startIdx);
      const expired = alignSeries(rawDates, d.expired).slice(trim.startIdx);
      const dash = dashSegment(trim.partialFromIdx);
      const ctx = addCanvas("gamesSection");
      destroyChart("games");
      state.charts.games = new Chart(ctx, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            applyDash(lineDataset("Started", started, "#22c55e"), dash),
            applyDash(lineDataset("Expired", expired, "#ef4444"), dash),
          ],
        },
        options: lineOpts(false),
      });
    } catch (ex) {
      showError("gamesSection", "Failed to load games.");
    }
  }

  async function loadCasualVsCedh() {
    try {
      const d = await fetchJson("casual-vs-cedh");
      const series = [
        { name: "Casual", points: d.casual },
        { name: "cEDH", points: d.cedh },
      ];
      if (!series[0].points.length && !series[1].points.length) {
        document.getElementById("casualVsCedhSection").innerHTML =
          '<div class="no-data">No data yet.</div>';
        destroyChart("casualVsCedh");
        return;
      }
      const ctx = addCanvas("casualVsCedhSection");
      destroyChart("casualVsCedh");
      state.charts.casualVsCedh = new Chart(ctx, {
        type: "line",
        data: buildStackedFromSeries(series, true),
        options: percentStackedOpts(),
      });
    } catch (ex) {
      showError("casualVsCedhSection", "Failed to load.");
    }
  }

  function buildStackedFromSeries(seriesList, asPercent) {
    const allLabels = new Set();
    seriesList.forEach(function (s) {
      s.points.forEach(function (p) {
        allLabels.add(p.date.slice(0, 10));
      });
    });
    const allSorted = Array.from(allLabels).sort();
    const trim = computeTrim(allSorted, currentBucket());
    const labels = allSorted.slice(trim.startIdx);
    const rawByIndex = seriesList.map(function (s) {
      const map = {};
      s.points.forEach(function (p) {
        map[p.date.slice(0, 10)] = p.count;
      });
      return labels.map(function (l) {
        return map[l] || 0;
      });
    });
    const totals = asPercent
      ? labels.map(function (_, i) {
          return rawByIndex.reduce(function (sum, row) {
            return sum + row[i];
          }, 0);
        })
      : null;
    const dash = dashSegment(trim.partialFromIdx);
    const datasets = seriesList.map(function (s, i) {
      const color = COLORS[i % COLORS.length];
      const data = rawByIndex[i].map(function (v, j) {
        if (!asPercent) return v;
        const total = totals[j];
        return total > 0 ? (v / total) * 100 : 0;
      });
      return {
        label: s.name,
        data: data,
        borderColor: color,
        backgroundColor: color + "DD",
        borderWidth: 1,
        tension: 0,
        fill: true,
        pointRadius: 0,
        segment: dash,
      };
    });
    return { labels: labels, datasets: datasets };
  }

  function percentStackedOpts() {
    const opts = lineOpts(true);
    opts.scales.y.max = 100;
    opts.scales.y.ticks = {
      color: TICK,
      callback: function (v) {
        return v + "%";
      },
    };
    opts.plugins.tooltip = {
      callbacks: {
        label: function (ctx) {
          return ctx.dataset.label + ": " + ctx.parsed.y.toFixed(1) + "%";
        },
      },
    };
    return opts;
  }

  async function loadServerPopularity() {
    try {
      const d = await fetchJson("server-popularity");
      if (!d.series.length) {
        document.getElementById("serverPopularitySection").innerHTML =
          '<div class="no-data">No data yet.</div>';
        destroyChart("serverPopularity");
        return;
      }
      const ctx = addCanvas("serverPopularitySection");
      destroyChart("serverPopularity");
      state.charts.serverPopularity = new Chart(ctx, {
        type: "line",
        data: buildStackedFromSeries(d.series, true),
        options: percentStackedOpts(),
      });
    } catch (ex) {
      showError("serverPopularitySection", "Failed to load.");
    }
  }

  function percentLineOpts(labelText) {
    const opts = lineOpts(false);
    opts.scales.y.max = 100;
    opts.scales.y.ticks = {
      color: TICK,
      callback: function (v) {
        return v + "%";
      },
    };
    opts.plugins.tooltip = {
      callbacks: {
        label: function (ctx) {
          return labelText + ": " + ctx.parsed.y.toFixed(1) + "%";
        },
      },
    };
    return opts;
  }

  async function loadBracketAdoption() {
    try {
      const d = await fetchJson("bracket-adoption");
      if (!d.rate.length) {
        document.getElementById("bracketAdoptionSection").innerHTML =
          '<div class="no-data">No data yet.</div>';
        destroyChart("bracketAdoption");
        return;
      }
      const rawDates = unifyDates([d.rate]);
      const trim = computeTrim(rawDates, currentBucket());
      const labels = rawDates.slice(trim.startIdx).map(function (s) {
        return s.slice(0, 10);
      });
      const rate = alignSeries(rawDates, d.rate).slice(trim.startIdx);
      const dash = dashSegment(trim.partialFromIdx);
      const ctx = addCanvas("bracketAdoptionSection");
      destroyChart("bracketAdoption");
      state.charts.bracketAdoption = new Chart(ctx, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            applyDash(lineDataset("Adoption Rate", rate, COLORS[7]), dash),
          ],
        },
        options: percentLineOpts("Adoption Rate"),
      });
    } catch (ex) {
      showError("bracketAdoptionSection", "Failed to load.");
    }
  }

  async function loadServicePopularity() {
    try {
      const d = await fetchJson("service-popularity");
      if (!d.series.length) {
        document.getElementById("servicePopularitySection").innerHTML =
          '<div class="no-data">No data yet.</div>';
        destroyChart("servicePopularity");
        return;
      }
      const ctx = addCanvas("servicePopularitySection");
      destroyChart("servicePopularity");
      state.charts.servicePopularity = new Chart(ctx, {
        type: "line",
        data: buildStackedFromSeries(d.series, true),
        options: percentStackedOpts(),
      });
    } catch (ex) {
      showError("servicePopularitySection", "Failed to load.");
    }
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

  function renderLanguageTable(sectionId, rows, label) {
    const el = document.getElementById(sectionId);
    if (!rows.length) {
      el.innerHTML = '<div class="no-data">No data yet.</div>';
      return;
    }
    const total = rows.reduce(function (acc, r) {
      return acc + r.count;
    }, 0);
    const body = rows
      .map(function (r) {
        const pct = total > 0 ? (r.count / total) * 100 : 0;
        return (
          "<tr><td>" +
          escapeHtml(r.locale) +
          '</td><td class="num">' +
          fmt(r.count) +
          '</td><td class="pct">' +
          pct.toFixed(1) +
          "%</td></tr>"
        );
      })
      .join("");
    el.innerHTML =
      '<table class="lang-table"><thead><tr><th>Locale</th><th style="text-align:right">' +
      escapeHtml(label) +
      '</th><th style="text-align:right">%</th></tr></thead><tbody>' +
      body +
      "</tbody></table>";
  }

  async function loadUserLanguages() {
    try {
      const d = await fetchJson("user-languages");
      renderLanguageTable("userLanguagesSection", d.rows, "Users");
    } catch (ex) {
      showError("userLanguagesSection", "Failed to load.");
    }
  }

  async function loadGameLanguages() {
    try {
      const d = await fetchJson("game-languages");
      renderLanguageTable("gameLanguagesSection", d.rows, "Games");
    } catch (ex) {
      showError("gameLanguagesSection", "Failed to load.");
    }
  }

  function renderTopGuildPerGameLanguage(sectionId, rows) {
    const el = document.getElementById(sectionId);
    if (!rows.length) {
      el.innerHTML = '<div class="no-data">No data yet.</div>';
      return;
    }
    const body = rows
      .map(function (r) {
        return (
          "<tr><td>" +
          escapeHtml(r.locale) +
          "</td><td>" +
          escapeHtml(r.guild_name) +
          '</td><td class="num">' +
          fmt(r.count) +
          "</td></tr>"
        );
      })
      .join("");
    el.innerHTML =
      '<table class="lang-table"><thead><tr><th>Locale</th><th>Server</th>' +
      '<th style="text-align:right">Games</th></tr></thead><tbody>' +
      body +
      "</tbody></table>";
  }

  async function loadTopGuildPerGameLanguage() {
    try {
      const d = await fetchJson("top-guild-per-game-language");
      renderTopGuildPerGameLanguage("topGuildPerGameLanguageSection", d.rows);
    } catch (ex) {
      showError("topGuildPerGameLanguageSection", "Failed to load.");
    }
  }

  function renderCountTable(sectionId, rows, keyField, label) {
    const el = document.getElementById(sectionId);
    if (!rows.length) {
      el.innerHTML = '<div class="no-data">No data yet.</div>';
      return;
    }
    const total = rows.reduce(function (acc, r) {
      return acc + r.count;
    }, 0);
    const body = rows
      .map(function (r) {
        const pct = total > 0 ? (r.count / total) * 100 : 0;
        return (
          "<tr><td>" +
          escapeHtml(String(r[keyField])) +
          '</td><td class="num">' +
          fmt(r.count) +
          '</td><td class="pct">' +
          pct.toFixed(1) +
          "%</td></tr>"
        );
      })
      .join("");
    el.innerHTML =
      '<table class="lang-table"><thead><tr><th>' +
      escapeHtml(label) +
      '</th><th style="text-align:right">Games</th><th style="text-align:right">%</th></tr></thead><tbody>' +
      body +
      "</tbody></table>";
  }

  function renderPlayerTable(sectionId, rows, countLabel) {
    const el = document.getElementById(sectionId);
    if (!rows.length) {
      el.innerHTML = '<div class="no-data">No data yet.</div>';
      return;
    }
    const body = rows
      .map(function (r) {
        const name = r.name || r.user_xid;
        const idCell = r.name
          ? ' <span class="player-xid">(' + escapeHtml(r.user_xid) + ")</span>"
          : "";
        return (
          "<tr><td>" +
          escapeHtml(name) +
          idCell +
          '</td><td class="num">' +
          fmt(r.count) +
          "</td></tr>"
        );
      })
      .join("");
    el.innerHTML =
      '<table class="lang-table"><thead><tr><th>Player</th><th style="text-align:right">' +
      escapeHtml(countLabel) +
      "</th></tr></thead><tbody>" +
      body +
      "</tbody></table>";
  }

  async function loadAvgWaitTime() {
    try {
      const d = await fetchJson("avg-wait-time");
      const series = d.series || [];
      if (!series.length) {
        document.getElementById("avgWaitTimeSection").innerHTML =
          '<div class="no-data">No data yet.</div>';
        destroyChart("avgWaitTime");
        return;
      }
      const rawDates = series.map(function (p) {
        return p.date;
      });
      const trim = computeTrim(rawDates, currentBucket());
      const labels = rawDates.slice(trim.startIdx).map(function (s) {
        return s.slice(0, 10);
      });
      const minutes = series.slice(trim.startIdx).map(function (p) {
        return p.minutes;
      });
      const dash = dashSegment(trim.partialFromIdx);
      const ctx = addCanvas("avgWaitTimeSection");
      destroyChart("avgWaitTime");
      state.charts.avgWaitTime = new Chart(ctx, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            applyDash(
              {
                label: "Avg Wait (minutes)",
                data: minutes,
                borderColor: "#fbbf24",
                backgroundColor: "rgba(251,191,36,0.1)",
                borderWidth: 2,
                tension: 0.3,
                fill: true,
                pointRadius: 0,
              },
              dash,
            ),
          ],
        },
        options: lineOpts(false),
      });
    } catch (ex) {
      showError("avgWaitTimeSection", "Failed to load.");
    }
  }

  async function loadPopularFormats() {
    try {
      const d = await fetchJson("popular-formats");
      renderCountTable("popularFormatsSection", d.rows, "format", "Format");
    } catch (ex) {
      showError("popularFormatsSection", "Failed to load.");
    }
  }

  async function loadPopularSeats() {
    try {
      const d = await fetchJson("popular-seats");
      renderCountTable("popularSeatsSection", d.rows, "seats", "Seats");
    } catch (ex) {
      showError("popularSeatsSection", "Failed to load.");
    }
  }

  async function loadTopPlayers() {
    try {
      const d = await fetchJson("top-players");
      renderPlayerTable("topPlayersSection", d.rows, "Games");
    } catch (ex) {
      showError("topPlayersSection", "Failed to load.");
    }
  }

  async function loadTopBlocked() {
    try {
      const d = await fetchJson("top-blocked");
      renderPlayerTable("topBlockedSection", d.rows, "Blocks");
    } catch (ex) {
      showError("topBlockedSection", "Failed to load.");
    }
  }

  async function loadHourOfDay() {
    try {
      const d = await fetchJson("hour-of-day");
      // Shift UTC bucket counts to the browser's local timezone. getTimezoneOffset
      // returns minutes west of UTC, so localHour = (utcHour - offset/60 + 24) % 24.
      const offsetHours = new Date().getTimezoneOffset() / 60;
      const local = new Array(24).fill(0);
      d.hours.forEach(function (p) {
        const lh = (((p.hour - offsetHours) % 24) + 24) % 24;
        local[Math.floor(lh)] += p.count;
      });
      const labels = local.map(function (_, i) {
        return String(i).padStart(2, "0") + ":00";
      });
      const ctx = addCanvas("hourOfDaySection");
      destroyChart("hourOfDay");
      state.charts.hourOfDay = new Chart(ctx, {
        type: "bar",
        data: {
          labels: labels,
          datasets: [
            {
              label: "Games",
              data: local,
              backgroundColor: "#818cf8",
              borderRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              grid: { color: GRID },
              ticks: { color: TICK, maxRotation: 0 },
            },
            y: {
              grid: { color: GRID },
              ticks: { color: TICK },
              beginAtZero: true,
            },
          },
        },
      });
    } catch (ex) {
      showError("hourOfDaySection", "Failed to load.");
    }
  }

  const DOW_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  async function loadDayOfWeek() {
    try {
      const d = await fetchJson("day-of-week");
      const counts = new Array(7).fill(0);
      d.days.forEach(function (p) {
        counts[p.dow] = p.count;
      });
      const ctx = addCanvas("dayOfWeekSection");
      destroyChart("dayOfWeek");
      state.charts.dayOfWeek = new Chart(ctx, {
        type: "bar",
        data: {
          labels: DOW_LABELS,
          datasets: [
            {
              label: "Games",
              data: counts,
              backgroundColor: "#22c55e",
              borderRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { color: GRID }, ticks: { color: TICK } },
            y: {
              grid: { color: GRID },
              ticks: { color: TICK },
              beginAtZero: true,
            },
          },
        },
      });
    } catch (ex) {
      showError("dayOfWeekSection", "Failed to load.");
    }
  }

  async function loadGamesPerPlayer() {
    try {
      const d = await fetchJson("games-per-player");
      document.getElementById("gamesPerPlayerTitle").textContent =
        "Games per Player (Median: " + d.median + ")";
      if (!d.histogram.length) {
        document.getElementById("gamesPerPlayerSection").innerHTML =
          '<div class="no-data">No data yet.</div>';
        destroyChart("gamesPerPlayer");
        return;
      }
      const medianBucket = Math.ceil(d.median);
      const ctx = addCanvas("gamesPerPlayerSection");
      destroyChart("gamesPerPlayer");
      state.charts.gamesPerPlayer = new Chart(ctx, {
        type: "bar",
        data: {
          labels: d.histogram.map(function (b) {
            return b.bucket;
          }),
          datasets: [
            {
              label: "Players",
              data: d.histogram.map(function (b) {
                return b.players;
              }),
              backgroundColor: d.histogram.map(function (b) {
                const n = parseFloat(b.bucket);
                return !isNaN(n) && n === medianBucket ? "#f59e0b" : "#60a5fa";
              }),
              borderRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            annotation: {
              annotations: {
                medianLine: {
                  type: "line",
                  xMin: d.median - 1,
                  xMax: d.median - 1,
                  borderColor: "#f59e0b",
                  borderWidth: 2,
                  borderDash: [6, 3],
                  label: {
                    display: true,
                    content: "Median: " + d.median,
                    position: "start",
                    color: "#fbbf24",
                    backgroundColor: "rgba(0,0,0,0.6)",
                  },
                },
              },
            },
          },
          scales: {
            x: { grid: { color: GRID }, ticks: { color: TICK } },
            y: {
              grid: { color: GRID },
              ticks: { color: TICK },
              beginAtZero: true,
            },
          },
        },
      });
    } catch (ex) {
      showError("gamesPerPlayerSection", "Failed to load.");
    }
  }

  const CLOUD_COLORS = [
    "#a78bfa",
    "#60a5fa",
    "#4ade80",
    "#f472b6",
    "#fbbf24",
    "#67e8f9",
    "#fb923c",
    "#a3e635",
  ];

  function renderTopRules(rows) {
    const el = document.getElementById("topRulesSection");
    if (!rows.length) {
      el.innerHTML = '<div class="no-data">No data yet.</div>';
      return;
    }
    const body = rows
      .map(function (r) {
        return (
          "<tr><td>" +
          escapeHtml(r.rule) +
          '</td><td class="num">' +
          fmt(r.count) +
          "</td></tr>"
        );
      })
      .join("");
    el.innerHTML =
      '<table class="lang-table"><thead><tr><th>Rule</th><th style="text-align:right">Games</th></tr></thead><tbody>' +
      body +
      "</tbody></table>";
  }

  function renderRulesCloud(ngrams) {
    const el = document.getElementById("rulesCloudSection");
    if (!ngrams.length) {
      el.innerHTML = '<div class="no-data">No data yet.</div>';
      return;
    }
    const maxCount = Math.max.apply(
      null,
      ngrams.map(function (n) {
        return n.count;
      }),
    );
    const minCount = Math.min.apply(
      null,
      ngrams.map(function (n) {
        return n.count;
      }),
    );
    const logMin = Math.log(minCount || 1);
    const logMax = Math.log(maxCount || 1);
    const logRange = logMax - logMin || 1;
    const shuffled = ngrams.slice().sort(function () {
      return Math.random() - 0.5;
    });
    const words = shuffled
      .map(function (n, i) {
        const logCount = Math.log(n.count || 1);
        const scale = (logCount - logMin) / logRange;
        const fontSize = 0.8 + scale * 1.2;
        const color = CLOUD_COLORS[i % CLOUD_COLORS.length];
        const rotation = (Math.random() - 0.5) * 8;
        const opacity = 0.75 + scale * 0.25;
        return (
          '<span class="cloud-word" style="font-size:' +
          fontSize +
          "rem;color:" +
          color +
          ";opacity:" +
          opacity +
          ";transform:rotate(" +
          rotation +
          'deg)" title="' +
          n.count +
          ' games">' +
          escapeHtml(n.phrase) +
          "</span>"
        );
      })
      .join("");
    el.innerHTML = '<div class="word-cloud">' + words + "</div>";
  }

  async function loadRules() {
    try {
      const d = await fetchJson("rules");
      renderTopRules(d.top_rules);
      renderRulesCloud(d.rule_ngrams);
    } catch (ex) {
      showError("topRulesSection", "Failed to load.");
      showError("rulesCloudSection", "Failed to load.");
    }
  }

  async function loadGuilds() {
    try {
      const res = await fetch("/admin/dashboard/guilds", {
        credentials: "same-origin",
      });
      if (!res.ok) return;
      const data = await res.json();
      const sel = document.getElementById("guildSelect");
      const current = state.guildXid;
      sel.innerHTML = '<option value="">All servers</option>';
      data.guilds.forEach(function (g) {
        const opt = document.createElement("option");
        opt.value = String(g.xid);
        opt.textContent = g.name ? g.name + " (" + g.xid + ")" : String(g.xid);
        sel.appendChild(opt);
      });
      if (current) sel.value = current;
      sel.disabled = state.guildMode === "all";
    } catch (ex) {
      /* leave dropdown disabled */
    }
  }

  function reloadAll() {
    loadTotals();
    loadSummary();
    loadAvgWaitTime();
    loadUsersActivity();
    loadGames();
    loadCasualVsCedh();
    loadServerPopularity();
    loadServicePopularity();
    loadBracketAdoption();
    loadHourOfDay();
    loadDayOfWeek();
    loadGamesPerPlayer();
    loadPopularFormats();
    loadPopularSeats();
    loadTopPlayers();
    loadTopBlocked();
    loadUserLanguages();
    loadGameLanguages();
    loadTopGuildPerGameLanguage();
    loadRules();
  }

  function bindControls() {
    document
      .querySelectorAll("#periodToggle .toggle-btn")
      .forEach(function (btn) {
        btn.addEventListener("click", function () {
          document
            .querySelectorAll("#periodToggle .toggle-btn")
            .forEach(function (b) {
              b.classList.remove("active");
            });
          btn.classList.add("active");
          state.period = btn.dataset.period;
          reloadAll();
        });
      });
    document
      .querySelectorAll("#guildModeToggle .toggle-btn")
      .forEach(function (btn) {
        btn.addEventListener("click", function () {
          document
            .querySelectorAll("#guildModeToggle .toggle-btn")
            .forEach(function (b) {
              b.classList.remove("active");
            });
          btn.classList.add("active");
          state.guildMode = btn.dataset.mode;
          const sel = document.getElementById("guildSelect");
          sel.disabled = state.guildMode === "all";
          if (state.guildMode === "all") state.guildXid = "";
          reloadAll();
        });
      });
    document
      .getElementById("guildSelect")
      .addEventListener("change", function (e) {
        state.guildXid = e.target.value;
        reloadAll();
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindControls();
    loadGuilds();
    reloadAll();
  });
})();
