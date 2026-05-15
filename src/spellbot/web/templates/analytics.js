/**
 * SpellBot Analytics Dashboard
 *
 * This script powers the analytics page. It expects a global ANALYTICS_CONFIG object
 * to be defined before this script loads:
 *   window.ANALYTICS_CONFIG = { baseUrl: "...", query: "...", expires: 1234567890 };
 */

(function () {
  "use strict";

  const config = window.ANALYTICS_CONFIG;
  if (!config) {
    console.error("ANALYTICS_CONFIG not defined");
    return;
  }

  /* Check if Chart.js is available - if not, graceful degradation was already handled */
  if (!window.CHART_AVAILABLE) {
    console.warn("Chart.js not available, analytics disabled");
    return;
  }

  const BASE_URL = config.baseUrl;
  const QUERY = config.query;
  const EXPIRES = config.expires;

  /* ── Countdown timer ── */
  (function () {
    const el = document.getElementById("countdown");
    function tick() {
      const left = Math.max(0, EXPIRES - Math.floor(Date.now() / 1000));
      const m = Math.floor(left / 60);
      const s = left % 60;
      el.textContent = m + ":" + (s < 10 ? "0" : "") + s;
      if (left <= 0) {
        el.textContent = "expired";
        return;
      }
      requestAnimationFrame(tick);
    }
    tick();
    setInterval(tick, 1000);
  })();

  /* ── Chart.js defaults ── */
  const GRID = "rgba(255,255,255,0.08)";
  const TICK = "#9ca3af";
  Chart.defaults.color = TICK;
  Chart.defaults.borderColor = GRID;

  const zoomOpts = {
    zoom: {
      drag: {
        enabled: true,
        backgroundColor: "rgba(129,140,248,0.2)",
        borderColor: "#818cf8",
        borderWidth: 1,
      },
      mode: "x",
      onZoomComplete: function ({ chart }) {
        const section = chart.canvas.closest(".chart-box");
        if (section && !section.querySelector(".zoom-hint")) {
          const hint = document.createElement("div");
          hint.className = "zoom-hint";
          hint.textContent = "Double-click to reset";
          hint.onclick = function () {
            resetChartZoom(chart);
          };
          section.appendChild(hint);
        }
      },
    },
  };

  function resetChartZoom(chart) {
    chart.resetZoom();
    const section = chart.canvas.closest(".chart-box");
    const hint = section?.querySelector(".zoom-hint");
    if (hint) hint.remove();
  }

  function setupZoomableChart(chart) {
    chart.canvas.addEventListener("dblclick", function () {
      resetChartZoom(chart);
    });
    return chart;
  }

  function lineOpts(xLabel, rawDates) {
    const xTicks = rawDates
      ? { color: TICK, maxRotation: 45, ...smartDateTicks(rawDates) }
      : { color: TICK, maxRotation: 45 };
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: true, labels: { color: "#e0e0e0", boxWidth: 12 } },
        zoom: zoomOpts,
      },
      scales: {
        x: {
          grid: { color: GRID },
          ticks: xTicks,
          title: { display: !!xLabel, text: xLabel || "", color: TICK },
        },
        y: { grid: { color: GRID }, ticks: { color: TICK }, beginAtZero: true },
      },
    };
  }

  function barOpts(indexAxis) {
    // For horizontal bars (indexAxis: "y"), use mode "y" to detect hover on row
    const axis = indexAxis || "x";
    return {
      indexAxis: axis,
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: axis === "y" ? "y" : "index", intersect: false },
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: GRID }, ticks: { color: TICK } },
        y: { grid: { color: GRID }, ticks: { color: TICK }, beginAtZero: true },
      },
    };
  }

  function stackedOptsWithDates(rawDates) {
    const xTicks = rawDates
      ? { color: TICK, maxRotation: 45, ...smartDateTicks(rawDates) }
      : { color: TICK, maxRotation: 45 };
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: true, labels: { color: "#e0e0e0", boxWidth: 12 } },
        zoom: zoomOpts,
      },
      scales: {
        x: { stacked: true, grid: { color: GRID }, ticks: xTicks },
        y: {
          stacked: true,
          grid: { color: GRID },
          ticks: { color: TICK },
          beginAtZero: true,
        },
      },
    };
  }

  /* ── Timezone helpers ── */
  const dateFmt = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  });
  const monthYearFmt = new Intl.DateTimeFormat(undefined, {
    month: "short",
    year: "numeric",
  });

  function fmtDay(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return dateFmt.format(new Date(y, m - 1, d));
  }
  function fmtMonthYear(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return monthYearFmt.format(new Date(y, m - 1, d));
  }
  function toDayMap(arr) {
    const m = {};
    arr.forEach((d) => (m[d.day] = d.count));
    return m;
  }
  function fmt(n) {
    return n.toLocaleString();
  }

  /* Smart date formatting based on visible range */
  function smartDateTicks(rawDates) {
    return {
      callback: function (value, index) {
        const chart = this.chart;
        const min = chart.scales.x.min;
        const max = chart.scales.x.max;
        const visibleCount = max - min + 1;
        const iso = rawDates[index];
        if (!iso) return "";
        return visibleCount <= 60 ? fmtDay(iso) : fmtMonthYear(iso);
      },
    };
  }

  /* ── Helpers for section state ── */
  function showError(sectionId, msg) {
    document.getElementById(sectionId).innerHTML =
      '<div class="section-error">' + msg + "</div>";
  }
  function showNoData(sectionId) {
    document.getElementById(sectionId).innerHTML =
      '<div class="no-data">No data yet.</div>';
  }
  function clearSection(sectionId) {
    document.getElementById(sectionId).innerHTML = "";
  }
  function addCanvas(sectionId, canvasId) {
    const el = document.getElementById(sectionId);
    el.innerHTML = '<canvas id="' + canvasId + '"></canvas>';
    return document.getElementById(canvasId);
  }

  /* ── Chart style constants ── */
  const svcColors = [
    "#818cf8",
    "#a78bfa",
    "#c084fc",
    "#e879f9",
    "#f472b6",
    "#fb7185",
    "#f97316",
    "#facc15",
    "#4ade80",
    "#22d3ee",
  ];
  const svcDoughnutOpts = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: {
        display: true,
        position: "right",
        labels: { color: "#e0e0e0", boxWidth: 12 },
      },
    },
  };
  const stackedOpts = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: true, labels: { color: "#e0e0e0", boxWidth: 12 } },
      zoom: zoomOpts,
    },
    scales: {
      x: {
        stacked: true,
        grid: { color: GRID },
        ticks: { color: TICK, maxRotation: 45 },
      },
      y: {
        stacked: true,
        grid: { color: GRID },
        ticks: { color: TICK },
        beginAtZero: true,
      },
    },
  };

  /* ── Global period state and caching ── */
  let currentPeriod = "30d";
  const dataCache = { "30d": {}, all: {} };
  const pendingRequests = { "30d": new Set(), all: new Set() };

  function periodLabel() {
    return currentPeriod === "all" ? "All Time" : "Last 30 Days";
  }

  /* Get user's timezone offset in hours (e.g., -7 for PDT, +5.5 for IST) */
  function getTimezoneOffsetHours() {
    return -new Date().getTimezoneOffset() / 60;
  }

  /* Get user's timezone abbreviation or UTC offset string */
  function getUserTimezone() {
    try {
      // Try to get timezone abbreviation (e.g., "PST", "EST")
      const formatter = new Intl.DateTimeFormat("en-US", {
        timeZoneName: "short",
      });
      const parts = formatter.formatToParts(new Date());
      const tzPart = parts.find((p) => p.type === "timeZoneName");
      if (tzPart) return tzPart.value;
    } catch (e) {
      // Fallback to UTC offset
    }
    const offset = getTimezoneOffsetHours();
    const sign = offset >= 0 ? "+" : "";
    return "UTC" + sign + offset;
  }

  /* Convert UTC hour (0-23) to local hour */
  function utcHourToLocal(utcHour) {
    const offset = getTimezoneOffsetHours();
    let localHour = (utcHour + offset) % 24;
    if (localHour < 0) localHour += 24;
    return Math.floor(localHour);
  }

  /* Get today's date in YYYY-MM-DD format (UTC) */
  function getTodayUTC() {
    return new Date().toISOString().split("T")[0];
  }

  /* Get today's date in YYYY-MM-DD format (local timezone) */
  function getTodayLocal() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  /* Filter out the current (incomplete) day from daily data.
     We filter both UTC and local "today" to handle all timezones. */
  function excludeToday(days) {
    const todayUTC = getTodayUTC();
    const todayLocal = getTodayLocal();
    return days.filter((d) => d !== todayUTC && d !== todayLocal);
  }

  function updateTitles() {
    const label = periodLabel();
    const weeksLabel = currentPeriod === "all" ? "All Time" : "Last 12 Weeks";
    document.getElementById("activityTitle").textContent =
      "Game Activity (" + label + ")";
    document.getElementById("bracketsTitle").textContent =
      "Games by Bracket (" + label + ")";
    document.getElementById("waitTimeTitle").textContent =
      "Average Wait Time (" + label + ")";
    document.getElementById("retentionTitle").textContent =
      "Player Retention (" + weeksLabel + ")";
    document.getElementById("growthTitle").textContent =
      "Cumulative Player Growth (" + label + ")";
    document.getElementById("formatsTitle").textContent =
      "Popular Formats (" + label + ")";
    document.getElementById("channelsTitle").textContent =
      "Busiest Channels (" + label + ")";
    document.getElementById("servicesTitle").textContent =
      "Popular Services (" + label + ")";
    document.getElementById("playersTitle").textContent =
      "Top Players (" + label + ")";
    document.getElementById("blockedTitle").textContent =
      "Most Blocked Players (" + label + ")";
    document.getElementById("hourOfDayTitle").textContent =
      "Games by Hour of Day, " + getUserTimezone() + " (" + label + ")";
    document.getElementById("dayOfWeekTitle").textContent =
      "Games by Day of Week (" + label + ")";
    document.getElementById("topRulesTitle").textContent =
      "Top Game Rules (" + label + ")";
    document.getElementById("rulesCloudTitle").textContent =
      "Rules Word Cloud (" + label + ")";
  }

  function showLoading(sectionId) {
    if (sectionId === "summarySection") {
      [
        "statFillRate",
        "statTotalGames",
        "statActivePlayers",
        "statRepeatRate",
      ].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '<div class="section-spinner"></div>';
      });
    } else {
      document.getElementById(sectionId).innerHTML =
        '<div class="section-loading"><div class="section-spinner"></div><div class="section-loading-text">Loading...</div></div>';
    }
  }

  function showSummaryError() {
    [
      "statFillRate",
      "statTotalGames",
      "statActivePlayers",
      "statRepeatRate",
    ].forEach((id) => {
      const el = document.getElementById(id);
      if (el)
        el.innerHTML =
          '<span style="color:#f87171;font-size:0.8rem">Error</span>';
    });
  }

  function switchPeriod(period) {
    if (period === currentPeriod) return;
    currentPeriod = period;
    document
      .querySelectorAll("#globalPeriodToggle .toggle-btn")
      .forEach((b) =>
        b.classList.toggle("active", b.dataset.period === period),
      );
    updateTitles();
    refreshAll();
  }

  // Expose switchPeriod globally for onclick handlers
  window.switchPeriod = switchPeriod;

  /* ── Individual render functions ── */

  function renderSummary(data) {
    document.getElementById("statFillRate").textContent = data.fill_rate + "%";
    document.getElementById("statTotalGames").textContent = fmt(
      data.total_games,
    );
    document.getElementById("statActivePlayers").textContent = fmt(
      data.active_players,
    );
    document.getElementById("statRepeatRate").textContent =
      data.repeat_player_rate + "%";
  }

  function renderActivity(data) {
    const gamesPerDay = data.games_per_day || [];
    const expiredPerDay = data.expired_per_day || [];
    const dailyNewUsers = data.daily_new_users || [];
    // Exclude today (incomplete day) from the chart
    const allDays = excludeToday(
      [
        ...new Set([
          ...gamesPerDay.map((d) => d.day),
          ...expiredPerDay.map((d) => d.day),
          ...dailyNewUsers.map((d) => d.day),
        ]),
      ].sort(),
    );
    if (allDays.length) {
      const gMap = toDayMap(gamesPerDay),
        eMap = toDayMap(expiredPerDay),
        nMap = toDayMap(dailyNewUsers);
      const canvas = addCanvas("activitySection", "chartDaily");
      setupZoomableChart(
        new Chart(canvas, {
          type: "line",
          data: {
            labels: allDays,
            datasets: [
              {
                label: "Games Started",
                data: allDays.map((d) => gMap[d] || 0),
                borderColor: "#818cf8",
                backgroundColor: "rgba(129,140,248,0.1)",
                fill: true,
                tension: 0.3,
              },
              {
                label: "Games Expired",
                data: allDays.map((d) => eMap[d] || 0),
                borderColor: "#f472b6",
                backgroundColor: "rgba(244,114,182,0.1)",
                fill: true,
                tension: 0.3,
              },
              {
                label: "New Users",
                data: allDays.map((d) => nMap[d] || 0),
                borderColor: "#4ade80",
                backgroundColor: "rgba(74,222,128,0.1)",
                fill: true,
                tension: 0.3,
              },
            ],
          },
          options: lineOpts("Date", allDays),
        }),
      );
    } else {
      showNoData("activitySection");
    }
  }

  function renderWaitTime(data) {
    // Exclude today (incomplete day) from the chart
    const allDays = (data.avg_wait_per_day || []).map((d) => d.day);
    const days = excludeToday(allDays);
    const daySet = new Set(days);
    const filteredData = (data.avg_wait_per_day || []).filter((d) =>
      daySet.has(d.day),
    );
    if (filteredData.length) {
      const canvas = addCanvas("waitTimeSection", "chartWaitTime");
      setupZoomableChart(
        new Chart(canvas, {
          type: "line",
          data: {
            labels: days,
            datasets: [
              {
                label: "Avg Wait (minutes)",
                data: filteredData.map((d) => d.minutes),
                borderColor: "#fbbf24",
                backgroundColor: "rgba(251,191,36,0.1)",
                fill: true,
                tension: 0.3,
              },
            ],
          },
          options: lineOpts("Date", days),
        }),
      );
    } else {
      showNoData("waitTimeSection");
    }
  }

  function renderBrackets(data) {
    const bracketData = data.games_by_bracket_per_day || [];
    // Exclude today (incomplete day) from the chart
    const bracketDays = excludeToday(
      [...new Set(bracketData.map((d) => d.day))].sort(),
    );
    if (bracketDays.length) {
      const bracketColorMap = {
        None: "#6b7280",
        "Bracket 1: Exhibition": "#22c55e",
        "Bracket 2: Core": "#eab308",
        "Bracket 3: Upgraded": "#3b82f6",
        "Bracket 4: Optimized": "#f97316",
        "Bracket 5: Competitive": "#ef4444",
      };
      const bracketOrder = [
        "None",
        "Bracket 1: Exhibition",
        "Bracket 2: Core",
        "Bracket 3: Upgraded",
        "Bracket 4: Optimized",
        "Bracket 5: Competitive",
      ];
      const brackets = bracketOrder.filter((b) =>
        bracketData.some((d) => d.bracket === b),
      );
      const bracketMap = {};
      bracketData.forEach((d) => {
        bracketMap[d.day + "|" + d.bracket] = d.count;
      });
      const canvas = addCanvas("bracketsSection", "chartBrackets");
      setupZoomableChart(
        new Chart(canvas, {
          type: "bar",
          data: {
            labels: bracketDays,
            datasets: brackets.map((b) => ({
              label: b === "None" ? "No Bracket" : b,
              data: bracketDays.map((d) => bracketMap[d + "|" + b] || 0),
              backgroundColor: bracketColorMap[b] || "#6b7280",
              borderRadius: 2,
            })),
          },
          options: stackedOptsWithDates(bracketDays),
        }),
      );
    } else {
      showNoData("bracketsSection");
    }
  }

  function renderRetention(data) {
    if (data.player_retention && data.player_retention.length) {
      const weeks = data.player_retention.map((d) => d.week);
      const canvas = addCanvas("retentionSection", "chartRetention");
      setupZoomableChart(
        new Chart(canvas, {
          type: "bar",
          data: {
            labels: weeks,
            datasets: [
              {
                label: "New Players",
                data: data.player_retention.map((d) => d.new),
                backgroundColor: "#22c55e",
                borderRadius: 2,
              },
              {
                label: "Returning Players",
                data: data.player_retention.map((d) => d.returning),
                backgroundColor: "#3b82f6",
                borderRadius: 2,
              },
            ],
          },
          options: stackedOptsWithDates(weeks),
        }),
      );
    } else {
      showNoData("retentionSection");
    }
  }

  function renderGrowth(data) {
    if (data.cumulative_players && data.cumulative_players.length) {
      const days = data.cumulative_players.map((d) => d.day);
      const canvas = addCanvas("growthSection", "chartGrowth");
      setupZoomableChart(
        new Chart(canvas, {
          type: "line",
          data: {
            labels: days,
            datasets: [
              {
                label: "Total Unique Players",
                data: data.cumulative_players.map((d) => d.total),
                borderColor: "#8b5cf6",
                backgroundColor: "rgba(139,92,246,0.1)",
                fill: true,
                tension: 0.3,
                pointRadius: 0,
              },
            ],
          },
          options: lineOpts("", days),
        }),
      );
    } else {
      showNoData("growthSection");
    }
  }

  function renderHistogram(data) {
    document.getElementById("histogramTitle").textContent =
      "Games per Player (Median: " + data.median_games + ")";
    if (data.games_histogram && data.games_histogram.length) {
      const medianVal = data.median_games;
      const canvas = addCanvas("histogramSection", "chartHistogram");
      new Chart(canvas, {
        type: "bar",
        data: {
          labels: data.games_histogram.map((d) => d.bucket),
          datasets: [
            {
              label: "Players",
              data: data.games_histogram.map((d) => d.players),
              backgroundColor: data.games_histogram.map((d) => {
                const b = parseFloat(d.bucket);
                return !isNaN(b) && b === Math.ceil(medianVal)
                  ? "#f59e0b"
                  : "#60a5fa";
              }),
              borderRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: "x",
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { display: false },
            annotation: {
              annotations: {
                medianLine: {
                  type: "line",
                  xMin: medianVal - 1,
                  xMax: medianVal - 1,
                  borderColor: "#f59e0b",
                  borderWidth: 2,
                  borderDash: [6, 3],
                  label: {
                    display: true,
                    content: "Median: " + medianVal,
                    position: "start",
                    color: "#fbbf24",
                    backgroundColor: "rgba(0,0,0,0.6)",
                  },
                },
              },
            },
          },
          scales: {
            x: {
              grid: { color: GRID },
              ticks: { color: TICK },
              title: { display: true, text: "Games Played", color: TICK },
            },
            y: {
              grid: { color: GRID },
              ticks: { color: TICK },
              beginAtZero: true,
              title: { display: true, text: "Players", color: TICK },
            },
          },
        },
      });
    } else {
      showNoData("histogramSection");
    }
  }

  function renderHourOfDay(data) {
    if (data.games_by_hour && data.games_by_hour.length) {
      // Convert UTC hours to local timezone and reorder
      const hourData = data.games_by_hour.map((d) => ({
        localHour: utcHourToLocal(d.hour),
        count: d.count,
      }));
      // Sort by local hour (0-23)
      hourData.sort((a, b) => a.localHour - b.localHour);

      const canvas = addCanvas("hourOfDaySection", "chartHourOfDay");
      new Chart(canvas, {
        type: "bar",
        data: {
          labels: hourData.map(
            (d) => d.localHour.toString().padStart(2, "0") + ":00",
          ),
          datasets: [
            {
              label: "Games",
              data: hourData.map((d) => d.count),
              backgroundColor: "#f472b6",
              borderRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { display: false } },
          scales: {
            x: {
              grid: { color: GRID },
              ticks: { color: TICK, maxRotation: 45, minRotation: 45 },
            },
            y: {
              grid: { color: GRID },
              ticks: { color: TICK },
              beginAtZero: true,
            },
          },
        },
      });
    } else {
      showNoData("hourOfDaySection");
    }
  }

  function renderDayOfWeek(data) {
    if (data.games_by_day && data.games_by_day.length) {
      const canvas = addCanvas("dayOfWeekSection", "chartDayOfWeek");
      new Chart(canvas, {
        type: "bar",
        data: {
          labels: data.games_by_day.map((d) => d.day),
          datasets: [
            {
              label: "Games",
              data: data.games_by_day.map((d) => d.count),
              backgroundColor: "#4ade80",
              borderRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
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
    } else {
      showNoData("dayOfWeekSection");
    }
  }

  function renderFormats(data) {
    if (data.popular_formats && data.popular_formats.length) {
      const canvas = addCanvas("formatsSection", "chartFormats");
      new Chart(canvas, {
        type: "bar",
        data: {
          labels: data.popular_formats.map((d) => d.format),
          datasets: [
            {
              label: "Games",
              data: data.popular_formats.map((d) => d.count),
              backgroundColor: "#a78bfa",
              borderRadius: 3,
            },
          ],
        },
        options: barOpts("y"),
      });
    } else {
      showNoData("formatsSection");
    }
  }

  function renderChannels(data) {
    if (data.busiest_channels && data.busiest_channels.length) {
      const canvas = addCanvas("channelsSection", "chartChannels");
      new Chart(canvas, {
        type: "bar",
        data: {
          labels: data.busiest_channels.map((d) => d.name),
          datasets: [
            {
              label: "Games",
              data: data.busiest_channels.map((d) => d.count),
              backgroundColor: "#67e8f9",
              borderRadius: 3,
            },
          ],
        },
        options: barOpts("y"),
      });
    } else {
      showNoData("channelsSection");
    }
  }

  function renderServices(data) {
    if (data.popular_services?.length) {
      const canvas = addCanvas("servicesSection", "chartServices");
      new Chart(canvas, {
        type: "doughnut",
        data: {
          labels: data.popular_services.map((d) => d.service),
          datasets: [
            {
              data: data.popular_services.map((d) => d.count),
              backgroundColor: svcColors,
            },
          ],
        },
        options: svcDoughnutOpts,
      });
    } else {
      showNoData("servicesSection");
    }
  }

  /* HTML escape to prevent XSS from user-controlled content like Discord names */
  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function renderPlayerRow(p, countLabel) {
    const leftBadge = p.left_server
      ? '<span class="left-badge" title="User has left the server and will be removed on next refresh">left</span>'
      : "";
    const rowClass = p.left_server ? ' class="left-server"' : "";
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
    const hasLeftServer = players.some((p) => p.left_server);
    if (!hasLeftServer) return "";
    return '<div class="left-server-note"><span class="left-badge">left</span> = User has left the server. They will not appear on the next page load.</div>';
  }

  function renderPlayers(data) {
    if (data.top_players?.length) {
      const section = document.getElementById("playersSection");
      section.innerHTML =
        '<table><thead><tr><th>Player</th><th>Discord ID</th><th style="text-align:right">Games</th></tr></thead><tbody>' +
        data.top_players.map((p) => renderPlayerRow(p, "Games")).join("") +
        "</tbody></table>" +
        renderLeftServerNote(data.top_players);
    } else {
      showNoData("playersSection");
    }
  }

  function renderBlocked(data) {
    if (data.top_blocked?.length) {
      const section = document.getElementById("blockedSection");
      section.innerHTML =
        '<table><thead><tr><th>Player</th><th>Discord ID</th><th style="text-align:right">Times Blocked</th></tr></thead><tbody>' +
        data.top_blocked
          .map((p) => renderPlayerRow(p, "Times Blocked"))
          .join("") +
        "</tbody></table>" +
        renderLeftServerNote(data.top_blocked);
    } else {
      showNoData("blockedSection");
    }
  }

  function renderTopRules(data) {
    if (data.top_rules?.length) {
      const section = document.getElementById("topRulesSection");
      section.innerHTML =
        '<table><thead><tr><th>Rule</th><th style="text-align:right">Games</th></tr></thead><tbody>' +
        data.top_rules
          .map(
            (r) =>
              `<tr><td>${escapeHtml(r.rule)}</td><td style="text-align:right">${r.count}</td></tr>`,
          )
          .join("") +
        "</tbody></table>";
    } else {
      showNoData("topRulesSection");
    }
  }

  function renderRulesCloud(data) {
    if (data.rule_ngrams?.length) {
      const section = document.getElementById("rulesCloudSection");
      const maxCount = Math.max(...data.rule_ngrams.map((n) => n.count));
      const minCount = Math.min(...data.rule_ngrams.map((n) => n.count));

      // Use logarithmic scale to handle large disparities in counts
      const logMin = Math.log(minCount || 1);
      const logMax = Math.log(maxCount || 1);
      const logRange = logMax - logMin || 1;

      // Color palette for variety
      const colors = [
        "#a78bfa", // purple
        "#60a5fa", // blue
        "#4ade80", // green
        "#f472b6", // pink
        "#fbbf24", // amber
        "#67e8f9", // cyan
        "#fb923c", // orange
        "#a3e635", // lime
      ];

      // Shuffle the ngrams for a more organic look
      const shuffled = [...data.rule_ngrams].sort(() => Math.random() - 0.5);

      // Generate word cloud as styled spans
      const words = shuffled
        .map((n, i) => {
          // Logarithmic scale for better distribution
          const logCount = Math.log(n.count || 1);
          const scale = (logCount - logMin) / logRange;
          // Scale font size between 0.8rem and 2rem
          const fontSize = 0.8 + scale * 1.2;
          // Pick color based on index for variety
          const color = colors[i % colors.length];
          // Slight random rotation for visual interest (-4 to 4 degrees)
          const rotation = (Math.random() - 0.5) * 8;
          // Vary opacity: higher count = more opaque
          const opacity = 0.75 + scale * 0.25;
          return `<span class="cloud-word" style="font-size:${fontSize}rem;color:${color};opacity:${opacity};transform:rotate(${rotation}deg)" title="${n.count} games">${escapeHtml(n.phrase)}</span>`;
        })
        .join("");

      section.innerHTML = `<div class="word-cloud">${words}</div>`;
    } else {
      showNoData("rulesCloudSection");
    }
  }

  /* ── Handle window resize for charts ── */
  let resizeTimeout;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(function () {
      Object.values(Chart.instances).forEach((chart) => {
        chart.canvas.style.width = "";
        chart.canvas.style.height = "";
        chart.canvas.removeAttribute("width");
        chart.canvas.removeAttribute("height");
        chart.resize();
      });
    }, 100);
  });

  /* ── Endpoint config ── */
  const endpoints = [
    { name: "summary", sectionId: "summarySection", render: renderSummary },
    { name: "activity", sectionId: "activitySection", render: renderActivity },
    { name: "wait-time", sectionId: "waitTimeSection", render: renderWaitTime },
    { name: "brackets", sectionId: "bracketsSection", render: renderBrackets },
    {
      name: "retention",
      sectionId: "retentionSection",
      render: renderRetention,
    },
    { name: "growth", sectionId: "growthSection", render: renderGrowth },
    {
      name: "histogram",
      sectionId: "histogramSection",
      render: renderHistogram,
    },
    {
      name: "hour-of-day",
      sectionId: "hourOfDaySection",
      render: renderHourOfDay,
    },
    {
      name: "day-of-week",
      sectionId: "dayOfWeekSection",
      render: renderDayOfWeek,
    },
    { name: "formats", sectionId: "formatsSection", render: renderFormats },
    { name: "channels", sectionId: "channelsSection", render: renderChannels },
    { name: "services", sectionId: "servicesSection", render: renderServices },
    { name: "players", sectionId: "playersSection", render: renderPlayers },
    { name: "blocked", sectionId: "blockedSection", render: renderBlocked },
    {
      name: "rules",
      sectionId: "topRulesSection",
      render: (data) => {
        renderTopRules(data);
        renderRulesCloud(data);
      },
    },
  ];

  function fetchEndpoint({ name, sectionId, render }) {
    const requestPeriod = currentPeriod;
    const cache = dataCache[requestPeriod];
    if (cache[name]) {
      render(cache[name]);
      return;
    }
    if (pendingRequests[requestPeriod].has(name)) {
      return;
    }
    showLoading(sectionId);
    pendingRequests[requestPeriod].add(name);
    const periodParam = "&period=" + requestPeriod;
    fetch(BASE_URL + "/" + name + QUERY + periodParam)
      .then((r) => {
        if (!r.ok) throw new Error("Failed");
        return r.json();
      })
      .then((data) => {
        pendingRequests[requestPeriod].delete(name);
        dataCache[requestPeriod][name] = data;
        if (currentPeriod === requestPeriod) {
          render(data);
        }
      })
      .catch(() => {
        pendingRequests[requestPeriod].delete(name);
        if (currentPeriod === requestPeriod) {
          if (sectionId === "summarySection") {
            showSummaryError();
          } else {
            showError(sectionId, "Failed to load");
          }
        }
      });
  }

  function refreshAll() {
    Object.values(Chart.instances).forEach((chart) => chart.destroy());
    endpoints.forEach((ep) => fetchEndpoint(ep));
  }

  /* ── Initial load ── */
  updateTitles();
  refreshAll();
})();
