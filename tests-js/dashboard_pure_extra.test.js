import { describe, it, expect } from "vitest";
import pure from "../src/spellbot/web/templates/dashboard_pure.js";

const {
  unifyDates,
  alignSeries,
  guildParam,
  qs,
  fmt,
  fmtDuration,
  avgCount,
  escapeHtml,
  heatColor,
} = pure;

describe("unifyDates", () => {
  it("returns the sorted union of dates across all series", () => {
    const a = [{ date: "2026-01-02" }, { date: "2026-01-01" }];
    const b = [{ date: "2026-01-03" }, { date: "2026-01-01" }];
    expect(unifyDates([a, b])).toEqual([
      "2026-01-01",
      "2026-01-02",
      "2026-01-03",
    ]);
  });

  it("returns an empty list for no series", () => {
    expect(unifyDates([])).toEqual([]);
  });
});

describe("alignSeries", () => {
  it("zero-fills missing dates and preserves order", () => {
    const series = [{ date: "2026-01-02", count: 5 }];
    const dates = ["2026-01-01", "2026-01-02", "2026-01-03"];
    expect(alignSeries(dates, series)).toEqual([
      { date: "2026-01-01", count: 0 },
      { date: "2026-01-02", count: 5 },
      { date: "2026-01-03", count: 0 },
    ]);
  });

  it("returns empty when there are no dates", () => {
    expect(alignSeries([], [{ date: "2026-01-01", count: 1 }])).toEqual([]);
  });
});

describe("guildParam", () => {
  it("returns 'all' when mode is all", () => {
    expect(guildParam("all", "12345")).toBe("all");
  });

  it("returns 'all' when there is no guildXid regardless of mode", () => {
    expect(guildParam("include", "")).toBe("all");
    expect(guildParam("exclude", null)).toBe("all");
  });

  it("returns not:<xid> for exclude mode", () => {
    expect(guildParam("exclude", "12345")).toBe("not:12345");
  });

  it("returns the xid for any other mode", () => {
    expect(guildParam("include", "12345")).toBe("12345");
  });
});

describe("qs", () => {
  it("URL-encodes period and the guild param", () => {
    expect(qs("30d", "include", "12345")).toBe("?period=30d&guild=12345");
    expect(qs("all", "all", null)).toBe("?period=all&guild=all");
    expect(qs("30d", "exclude", "12345")).toBe("?period=30d&guild=not%3A12345");
  });
});

describe("fmt", () => {
  it("returns an em dash for null and undefined", () => {
    expect(fmt(null)).toBe("—");
    expect(fmt(undefined)).toBe("—");
  });

  it("formats numbers with grouping separators", () => {
    expect(fmt(0)).toBe("0");
    expect(fmt(1234)).toBe("1,234");
    expect(fmt("1234")).toBe("1,234");
  });
});

describe("fmtDuration", () => {
  it("returns an em dash for null and undefined", () => {
    expect(fmtDuration(null)).toBe("—");
    expect(fmtDuration(undefined)).toBe("—");
  });

  it("clamps negative values to 0s", () => {
    expect(fmtDuration(-5)).toBe("0s");
  });

  it("formats seconds under one minute as Ns", () => {
    expect(fmtDuration(0)).toBe("0s");
    expect(fmtDuration(59)).toBe("59s");
  });

  it("formats minutes under one hour as Nm (floors)", () => {
    expect(fmtDuration(60)).toBe("1m");
    expect(fmtDuration(90)).toBe("1m");
    expect(fmtDuration(3599)).toBe("59m");
  });

  it("formats hours under one day as Nh or Nh Mm", () => {
    expect(fmtDuration(3600)).toBe("1h");
    expect(fmtDuration(3600 + 23 * 60)).toBe("1h 23m");
  });

  it("formats days as Nd or Nd Hh", () => {
    expect(fmtDuration(86400)).toBe("1d");
    expect(fmtDuration(86400 + 4 * 3600)).toBe("1d 4h");
  });
});

describe("avgCount", () => {
  it("returns 0 for empty or missing input", () => {
    expect(avgCount([])).toBe(0);
    expect(avgCount(null)).toBe(0);
    expect(avgCount(undefined)).toBe(0);
  });

  it("rounds the arithmetic mean of count values", () => {
    expect(avgCount([{ count: 1 }, { count: 2 }, { count: 4 }])).toBe(2);
    expect(avgCount([{ count: 1 }, { count: 2 }])).toBe(2);
  });
});

describe("escapeHtml", () => {
  it("escapes the five HTML metacharacters", () => {
    expect(escapeHtml(`<a href="x">&'</a>`)).toBe(
      "&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;",
    );
  });

  it("coerces non-string input via String()", () => {
    expect(escapeHtml(42)).toBe("42");
    expect(escapeHtml(null)).toBe("null");
  });
});

describe("heatColor", () => {
  it("returns the lo color for zero or missing maxValue", () => {
    expect(heatColor(5, 0)).toBe("rgb(30,58,138)");
    expect(heatColor(0, 10)).toBe("rgb(30,58,138)");
  });

  it("returns the hi color when value equals maxValue", () => {
    expect(heatColor(10, 10)).toBe("rgb(244,114,182)");
  });

  it("interpolates on a sqrt scale between lo and hi", () => {
    // sqrt(0.25) = 0.5 -> midpoint
    const mid = heatColor(1, 4);
    expect(mid).toBe(
      "rgb(" +
        Math.round(30 + (244 - 30) * 0.5) +
        "," +
        Math.round(58 + (114 - 58) * 0.5) +
        "," +
        Math.round(138 + (182 - 138) * 0.5) +
        ")",
    );
  });

  it("honors custom lo/hi rgb triples", () => {
    expect(heatColor(0, 10, [0, 0, 0], [255, 255, 255])).toBe("rgb(0,0,0)");
    expect(heatColor(10, 10, [0, 0, 0], [255, 255, 255])).toBe(
      "rgb(255,255,255)",
    );
  });
});
