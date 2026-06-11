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

  // Convenience wrapper that binds the current period and clock to the pure
  // `computeTrim` helper. Most callers just need the trim indices for the
  // active filter selection.
  function trimNow(rawDates) {
    const now = Date.now();
    return computeTrim(
      rawDates,
      currentBucket(state.period),
      now,
      periodStartMs(state.period, now),
    );
  }

  function dashSegment(partialFromIdx) {
    return {
      borderDash: function (ctx) {
        return ctx.p1DataIndex >= partialFromIdx ? [6, 4] : undefined;
      },
    };
  }

  async function fetchJson(path) {
    const res = await fetch(
      "/admin/dashboard/" +
        path +
        qs(state.period, state.guildMode, state.guildXid),
      { credentials: "same-origin" },
    );
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
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

  // Markup mirrored from dashboard.html.j2 so a filter-driven reload reverts
  // every panel to the same loading treatment used on the initial page render.
  const SECTION_LOADING_HTML =
    '<div class="section-loading">' +
    '<div class="section-spinner"></div>' +
    '<div class="section-loading-text">Loading...</div>' +
    "</div>";
  const STAT_LOADING_HTML = '<div class="section-spinner"></div>';

  function showAllLoading() {
    // Tear down live charts first so Chart.js releases its canvases before we
    // wipe the containing element's children.
    Object.keys(state.charts).forEach(destroyChart);
    document.querySelectorAll(".chart-box, .table-box").forEach(function (el) {
      el.innerHTML = SECTION_LOADING_HTML;
    });
    document.querySelectorAll(".stat-value").forEach(function (el) {
      el.innerHTML = STAT_LOADING_HTML;
    });
    document.getElementById("bucketLabel").textContent = "—";
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
      document.getElementById("statFillRate").textContent =
        (data.fill_rate == null ? 0 : data.fill_rate) + "%";
      document.getElementById("bucketLabel").textContent = data.bucket || "—";
      setBracketStats(data.brackets);
    } catch (ex) {
      ["statGames", "statPlayers", "statServers", "statFillRate"].forEach(
        function (id) {
          document.getElementById(id).textContent = "—";
        },
      );
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

  function applyDash(dataset, dash) {
    dataset.segment = dash;
    return dataset;
  }

  async function loadGameActivity() {
    let users;
    let games;
    try {
      [users, games] = await Promise.all([
        fetchJson("users-activity"),
        fetchJson("games"),
      ]);
    } catch (ex) {
      showError("gameActivitySection", "Failed to load game activity.");
      ["statWau", "statMau", "statDauMau"].forEach(function (id) {
        document.getElementById(id).textContent = "—";
      });
      return;
    }
    document.getElementById("statDauMau").textContent =
      (users.dau_mau || 0) + "%";
    document.getElementById("statWau").textContent = fmt(avgCount(users.wau));
    document.getElementById("statMau").textContent = fmt(avgCount(users.mau));
    const rawDates = unifyDates([
      users.new_users,
      games.started,
      games.expired,
    ]);
    const trim = trimNow(rawDates);
    const labels = rawDates.slice(trim.startIdx).map(function (s) {
      return s.slice(0, 10);
    });
    const newUsers = alignSeries(rawDates, users.new_users).slice(
      trim.startIdx,
    );
    const started = alignSeries(rawDates, games.started).slice(trim.startIdx);
    const expired = alignSeries(rawDates, games.expired).slice(trim.startIdx);
    const dash = dashSegment(trim.partialFromIdx);
    const ctx = addCanvas("gameActivitySection");
    destroyChart("gameActivity");
    state.charts.gameActivity = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          applyDash(lineDataset("New Users", newUsers, "#4ade80"), dash),
          applyDash(lineDataset("Started Games", started, "#818cf8"), dash),
          applyDash(lineDataset("Expired Games", expired, "#f472b6"), dash),
        ],
      },
      options: lineOpts(false),
    });
  }

  async function loadPlayerGrowth() {
    try {
      const d = await fetchJson("player-growth");
      const series = d.cumulative_players || [];
      const rawDates = series.map(function (p) {
        return p.date;
      });
      const trim = trimNow(rawDates);
      const labels = rawDates.slice(trim.startIdx).map(function (s) {
        return s.slice(0, 10);
      });
      const points = series.slice(trim.startIdx);
      const dash = dashSegment(trim.partialFromIdx);
      const ctx = addCanvas("playerGrowthSection");
      destroyChart("playerGrowth");
      state.charts.playerGrowth = new Chart(ctx, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            applyDash(
              lineDataset("Total Unique Players", points, "#8b5cf6", true),
              dash,
            ),
          ],
        },
        options: lineOpts(false),
      });
    } catch (ex) {
      showError("playerGrowthSection", "Failed to load player growth.");
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
    const trim = trimNow(allSorted);
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
      const totals = d.totals || [];
      const colorByName = {};
      d.series.forEach(function (s, i) {
        colorByName[s.name] = COLORS[i % COLORS.length];
      });
      let chart = null;
      if (!d.series.length) {
        document.getElementById("serverPopularitySection").innerHTML =
          '<div class="no-data">No data yet.</div>';
        destroyChart("serverPopularity");
      } else {
        const ctx = addCanvas("serverPopularitySection");
        destroyChart("serverPopularity");
        const opts = percentStackedOpts();
        // Wrap the built-in legend handler so toggling a series in the chart
        // also strikes through the matching row in the table.
        const defaultOnClick = Chart.defaults.plugins.legend.onClick;
        opts.plugins.legend = opts.plugins.legend || {};
        opts.plugins.legend.onClick = function (e, item, legend) {
          defaultOnClick.call(this, e, item, legend);
          setServerPopularityRowHidden(item.text, item.hidden);
        };
        chart = new Chart(ctx, {
          type: "line",
          data: buildStackedFromSeries(d.series, true),
          options: opts,
        });
        state.charts.serverPopularity = chart;
      }
      renderServerPopularityTable(totals, colorByName, chart);
    } catch (ex) {
      showError("serverPopularitySection", "Failed to load.");
      showError("serverPopularityTable", "Failed to load.");
    }
  }

  function renderServerPopularityTable(rows, colorByName, chart) {
    const el = document.getElementById("serverPopularityTable");
    if (!rows.length) {
      el.innerHTML = '<div class="no-data">No servers with 10+ games.</div>';
      return;
    }
    const datasetIndexByName = {};
    if (chart) {
      chart.data.datasets.forEach(function (ds, i) {
        datasetIndexByName[ds.label] = i;
      });
    }
    const body = rows
      .map(function (r) {
        const color = colorByName[r.name];
        const inChart = Object.prototype.hasOwnProperty.call(
          datasetIndexByName,
          r.name,
        );
        const swatch = color
          ? '<span style="background:' + color + '"></span>'
          : "";
        const trAttrs = inChart
          ? ' class="interactive" data-name="' + escapeHtml(r.name) + '"'
          : "";
        return (
          "<tr" +
          trAttrs +
          '><td class="swatch">' +
          swatch +
          "</td><td>" +
          escapeHtml(r.name) +
          '</td><td class="num">' +
          fmt(r.count) +
          "</td></tr>"
        );
      })
      .join("");
    el.innerHTML =
      '<table class="lang-table"><thead><tr><th></th><th>Server</th>' +
      '<th style="text-align:right">Games</th></tr></thead><tbody>' +
      body +
      "</tbody></table>";

    if (!chart) return;
    el.querySelectorAll("tr[data-name]").forEach(function (row) {
      row.addEventListener("click", function () {
        const name = row.getAttribute("data-name");
        const idx = datasetIndexByName[name];
        if (idx === undefined) return;
        const willHide = chart.isDatasetVisible(idx);
        if (willHide) chart.hide(idx);
        else chart.show(idx);
        setServerPopularityRowHidden(name, willHide);
      });
    });
  }

  function setServerPopularityRowHidden(name, hidden) {
    const el = document.getElementById("serverPopularityTable");
    if (!el) return;
    el.querySelectorAll("tr[data-name]").forEach(function (row) {
      if (row.getAttribute("data-name") === name) {
        row.classList.toggle("series-hidden", !!hidden);
      }
    });
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
      const leaders = d.leaders || [];
      if (!d.rate.length) {
        document.getElementById("bracketAdoptionSection").innerHTML =
          '<div class="no-data">No data yet.</div>';
        destroyChart("bracketAdoption");
      } else {
        const rawDates = unifyDates([d.rate]);
        const trim = trimNow(rawDates);
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
      }
      renderBracketLeadersTable(leaders);
    } catch (ex) {
      showError("bracketAdoptionSection", "Failed to load.");
      showError("bracketLeadersTable", "Failed to load.");
    }
  }

  function renderBracketLeadersTable(rows) {
    const el = document.getElementById("bracketLeadersTable");
    if (!el) return;
    if (!rows.length) {
      el.innerHTML = '<div class="no-data">No data yet.</div>';
      return;
    }
    const body = rows
      .map(function (r) {
        const server = r.server ? escapeHtml(r.server) : "—";
        return (
          "<tr><td>" +
          escapeHtml(r.bracket) +
          "</td><td>" +
          server +
          '</td><td class="num">' +
          fmt(r.count) +
          "</td></tr>"
        );
      })
      .join("");
    el.innerHTML =
      '<table class="lang-table"><thead><tr><th>Bracket</th><th>Top Server</th>' +
      '<th style="text-align:right">Games</th></tr></thead><tbody>' +
      body +
      "</tbody></table>";
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

  async function loadGuildLanguages() {
    try {
      const d = await fetchJson("guild-languages");
      renderLanguageTable("guildLanguagesSection", d.rows, "Servers");
    } catch (ex) {
      showError("guildLanguagesSection", "Failed to load.");
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
      const trim = trimNow(rawDates);
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

  async function loadActivityHeatmap() {
    try {
      const d = await fetchJson("activity-heatmap");
      const el = document.getElementById("activityHeatmapSection");
      if (!d.cells.length) {
        el.innerHTML = '<div class="no-data">No data yet.</div>';
        return;
      }
      // Shift UTC dow/hour to local time. Hour shift may flip the dow.
      const offsetHours = new Date().getTimezoneOffset() / 60;
      const grid = [];
      for (let i = 0; i < 7; i += 1) grid.push(new Array(24).fill(0));
      d.cells.forEach(function (c) {
        const totalHour = c.dow * 24 + c.hour - offsetHours;
        const wrapped = ((totalHour % 168) + 168) % 168;
        const lh = Math.floor(wrapped) % 24;
        const ld = Math.floor(wrapped / 24) % 7;
        grid[ld][lh] += c.count;
      });
      let maxValue = 0;
      grid.forEach(function (row) {
        row.forEach(function (v) {
          if (v > maxValue) maxValue = v;
        });
      });
      const cols = [];
      for (let h = 0; h < 24; h += 1) {
        cols.push(
          '<div class="hm-col">' +
            (h % 3 === 0 ? String(h).padStart(2, "0") : "") +
            "</div>",
        );
      }
      const rows = grid
        .map(function (row, d2) {
          const cells = row
            .map(function (v, h) {
              return (
                '<div class="hm-cell" style="background:' +
                heatColor(v, maxValue) +
                '" title="' +
                DOW_LABELS[d2] +
                " " +
                String(h).padStart(2, "0") +
                ":00 — " +
                v +
                ' games"></div>'
              );
            })
            .join("");
          return '<div class="hm-row">' + DOW_LABELS[d2] + "</div>" + cells;
        })
        .join("");
      el.innerHTML =
        '<div class="heatmap" style="grid-template-columns:40px repeat(24, minmax(0, 1fr))">' +
        '<div class="hm-corner"></div>' +
        cols.join("") +
        rows +
        "</div>" +
        '<div class="heatmap-legend"><span>less</span>' +
        '<span class="hm-scale"></span>' +
        "<span>more (max: " +
        fmt(maxValue) +
        ")</span></div>";
    } catch (ex) {
      showError("activityHeatmapSection", "Failed to load.");
    }
  }

  async function loadCohortRetention() {
    try {
      const d = await fetchJson("cohort-retention");
      const el = document.getElementById("cohortRetentionSection");
      if (!d.cohorts.length) {
        el.innerHTML = '<div class="no-data">No data yet.</div>';
        return;
      }
      const maxWeeks = d.max_weeks;
      const header = ['<th class="cohort-label">Cohort (size)</th>'];
      for (let i = 0; i <= maxWeeks; i += 1) header.push("<th>W" + i + "</th>");
      const body = d.cohorts
        .map(function (c) {
          const byOffset = {};
          c.weeks.forEach(function (w) {
            byOffset[w.offset] = w;
          });
          const cells = [];
          for (let i = 0; i <= maxWeeks; i += 1) {
            const w = byOffset[i];
            if (!w) {
              cells.push("<td></td>");
            } else {
              cells.push(
                '<td class="cohort-cell" style="background:' +
                  heatColor(w.pct, 100) +
                  '" title="' +
                  w.count +
                  " of " +
                  c.size +
                  ' players">' +
                  w.pct.toFixed(0) +
                  "%</td>",
              );
            }
          }
          return (
            '<tr><td class="cohort-label">' +
            escapeHtml(c.cohort.slice(0, 10)) +
            " (" +
            fmt(c.size) +
            ")</td>" +
            cells.join("") +
            "</tr>"
          );
        })
        .join("");
      el.innerHTML =
        '<div style="overflow-x:auto"><table class="cohort-table"><thead><tr>' +
        header.join("") +
        "</tr></thead><tbody>" +
        body +
        "</tbody></table></div>";
    } catch (ex) {
      showError("cohortRetentionSection", "Failed to load.");
    }
  }

  async function loadWaitTimeDistribution() {
    try {
      const d = await fetchJson("wait-time-distribution");
      const sections = [d.p50, d.p95, d.p99];
      if (!sections[0].length) {
        document.getElementById("waitTimeDistributionSection").innerHTML =
          '<div class="no-data">No data yet.</div>';
        destroyChart("waitTimeDistribution");
        return;
      }
      const rawDates = sections[0].map(function (p) {
        return p.date;
      });
      const trim = trimNow(rawDates);
      const labels = rawDates.slice(trim.startIdx).map(function (s) {
        return s.slice(0, 10);
      });
      const dash = dashSegment(trim.partialFromIdx);
      function ds(label, series, color) {
        return applyDash(
          {
            label: label,
            data: series.slice(trim.startIdx).map(function (p) {
              return p.minutes;
            }),
            borderColor: color,
            backgroundColor: color + "33",
            borderWidth: 2,
            tension: 0.3,
            fill: false,
            pointRadius: 0,
          },
          dash,
        );
      }
      const ctx = addCanvas("waitTimeDistributionSection");
      destroyChart("waitTimeDistribution");
      state.charts.waitTimeDistribution = new Chart(ctx, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            ds("p50", d.p50, "#4ade80"),
            ds("p95", d.p95, "#fbbf24"),
            ds("p99", d.p99, "#ef4444"),
          ],
        },
        options: lineOpts(false),
      });
    } catch (ex) {
      showError("waitTimeDistributionSection", "Failed to load.");
    }
  }

  function loadAdoptionRateChart(sectionId, chartKey, fetchPath, label, color) {
    return (async function () {
      try {
        const d = await fetchJson(fetchPath);
        const series = d.rate || [];
        if (!series.length) {
          document.getElementById(sectionId).innerHTML =
            '<div class="no-data">No data yet.</div>';
          destroyChart(chartKey);
          return;
        }
        const rawDates = series.map(function (p) {
          return p.date;
        });
        const trim = trimNow(rawDates);
        const labels = rawDates.slice(trim.startIdx).map(function (s) {
          return s.slice(0, 10);
        });
        const points = series.slice(trim.startIdx);
        const dash = dashSegment(trim.partialFromIdx);
        const ctx = addCanvas(sectionId);
        destroyChart(chartKey);
        const opts = percentLineOpts(label);
        opts.plugins.legend = { display: false };
        state.charts[chartKey] = new Chart(ctx, {
          type: "line",
          data: {
            labels: labels,
            datasets: [
              applyDash(
                {
                  label: label,
                  data: points.map(function (p) {
                    return p.count;
                  }),
                  borderColor: color,
                  backgroundColor: color + "33",
                  borderWidth: 2,
                  tension: 0.3,
                  fill: true,
                  pointRadius: 0,
                },
                dash,
              ),
            ],
          },
          options: opts,
        });
      } catch (ex) {
        showError(sectionId, "Failed to load.");
      }
    })();
  }

  function loadVoiceAdoption() {
    return loadAdoptionRateChart(
      "voiceAdoptionSection",
      "voiceAdoption",
      "voice-adoption",
      "Voice channel",
      "#06b6d4",
    );
  }

  function loadBlindAdoption() {
    return loadAdoptionRateChart(
      "blindAdoptionSection",
      "blindAdoption",
      "blind-adoption",
      "Blind games",
      "#a855f7",
    );
  }

  function loadMythicVerification() {
    return loadAdoptionRateChart(
      "mythicVerificationSection",
      "mythicVerification",
      "mythic-verification",
      "Verified",
      "#22c55e",
    );
  }

  async function loadQueueDepth() {
    try {
      const d = await fetchJson("queue-depth");
      const el = document.getElementById("queueDepthSection");
      const header =
        '<div class="queue-depth-total">' +
        fmt(d.total) +
        ' <span class="stat-unit">players waiting</span></div>';
      if (!d.by_format.length) {
        el.innerHTML =
          header + '<div class="no-data">No one is queued right now.</div>';
        return;
      }
      const body = d.by_format
        .map(function (r) {
          return (
            "<tr><td>" +
            escapeHtml(r.format) +
            '</td><td class="num">' +
            fmt(r.count) +
            "</td></tr>"
          );
        })
        .join("");
      el.innerHTML =
        header +
        '<table class="lang-table"><thead><tr><th>Format</th>' +
        '<th style="text-align:right">Players Queued</th></tr></thead><tbody>' +
        body +
        "</tbody></table>";
    } catch (ex) {
      showError("queueDepthSection", "Failed to load.");
    }
  }

  async function loadActiveQueues() {
    try {
      const d = await fetchJson("active-queues");
      const el = document.getElementById("activeQueuesSection");
      if (!d.rows.length) {
        el.innerHTML = '<div class="no-data">No active queues right now.</div>';
        return;
      }
      const body = d.rows
        .map(function (r) {
          const url =
            "https://discord.com/channels/" +
            encodeURIComponent(r.guild_xid) +
            "/" +
            encodeURIComponent(r.channel_xid);
          const guildName = r.guild_name || r.guild_xid;
          const channelName = r.channel_name || r.channel_xid;
          return (
            "<tr><td>" +
            escapeHtml(guildName) +
            '</td><td><a href="' +
            url +
            '" target="_blank" rel="noopener noreferrer">#' +
            escapeHtml(channelName) +
            "</a></td><td>" +
            escapeHtml(r.format) +
            "</td><td>" +
            escapeHtml(r.bracket) +
            '</td><td class="num">' +
            fmt(r.players) +
            '</td><td class="num">' +
            escapeHtml(fmtDuration(r.wait_seconds)) +
            "</td></tr>"
          );
        })
        .join("");
      el.innerHTML =
        '<table class="lang-table"><thead><tr><th>Server</th>' +
        "<th>Channel</th><th>Format</th><th>Bracket</th>" +
        '<th style="text-align:right">Players</th>' +
        '<th style="text-align:right">Wait</th>' +
        "</tr></thead><tbody>" +
        body +
        "</tbody></table>";
    } catch (ex) {
      showError("activeQueuesSection", "Failed to load.");
    }
  }

  function reloadAll() {
    showAllLoading();
    loadTotals();
    loadSummary();
    loadAvgWaitTime();
    loadGameActivity();
    loadPlayerGrowth();
    loadCasualVsCedh();
    loadServerPopularity();
    loadServicePopularity();
    loadBracketAdoption();
    loadHourOfDay();
    loadDayOfWeek();
    loadActivityHeatmap();
    loadCohortRetention();
    loadWaitTimeDistribution();
    loadVoiceAdoption();
    loadBlindAdoption();
    loadMythicVerification();
    loadQueueDepth();
    loadActiveQueues();
    loadGamesPerPlayer();
    loadPopularFormats();
    loadPopularSeats();
    loadTopPlayers();
    loadTopBlocked();
    loadUserLanguages();
    loadGameLanguages();
    loadGuildLanguages();
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

  // Owner-only SQL console. The textarea/button only exist in the DOM when the
  // template rendered for the bot owner, and the /admin/dashboard/sql endpoint
  // re-checks ownership server-side, so this is purely the client wiring.
  function bindSqlConsole() {
    if (!window.SQL_CONSOLE_ENABLED) return;
    const runBtn = document.getElementById("sqlRunBtn");
    const textarea = document.getElementById("sqlQuery");
    const statusEl = document.getElementById("sqlStatus");
    const resultEl = document.getElementById("sqlResult");
    if (!runBtn || !textarea) return;

    function renderResult(data) {
      if (!data.columns || !data.columns.length) {
        resultEl.innerHTML =
          '<div class="sql-status">Query ran (no result set returned).</div>';
        return;
      }
      const head = data.columns
        .map(function (c) {
          return "<th>" + escapeHtml(c) + "</th>";
        })
        .join("");
      const body = data.rows
        .map(function (row) {
          const cells = row
            .map(function (cell) {
              if (cell === null)
                return '<td class="sql-null">NULL</td>';
              return "<td>" + escapeHtml(String(cell)) + "</td>";
            })
            .join("");
          return "<tr>" + cells + "</tr>";
        })
        .join("");
      resultEl.innerHTML =
        '<table class="lang-table"><thead><tr>' +
        head +
        "</tr></thead><tbody>" +
        body +
        "</tbody></table>";
    }

    async function runQuery() {
      const query = textarea.value.trim();
      if (!query) return;
      runBtn.disabled = true;
      statusEl.textContent = "Running...";
      resultEl.innerHTML = "";
      const started = Date.now();
      try {
        const res = await fetch("/admin/dashboard/sql", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: query }),
        });
        const data = await res.json();
        const elapsed = ((Date.now() - started) / 1000).toFixed(2);
        if (data.error) {
          statusEl.textContent = "Error (" + elapsed + "s)";
          resultEl.innerHTML =
            '<div class="sql-error">' + escapeHtml(data.error) + "</div>";
          return;
        }
        renderResult(data);
        statusEl.textContent =
          data.row_count +
          (data.row_count === 1 ? " row" : " rows") +
          (data.truncated ? " (truncated)" : "") +
          " in " +
          elapsed +
          "s";
      } catch (ex) {
        statusEl.textContent = "Request failed.";
        resultEl.innerHTML =
          '<div class="sql-error">' + escapeHtml(String(ex)) + "</div>";
      } finally {
        runBtn.disabled = false;
      }
    }

    runBtn.addEventListener("click", runQuery);
    textarea.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        runQuery();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindControls();
    bindSqlConsole();
    loadGuilds();
    reloadAll();
  });
})();
