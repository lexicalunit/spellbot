import { describe, it, expect } from "vitest";
import common from "../src/spellbot/web/templates/chart_common_pure.js";

const { escapeHtml, fmt, getTimezoneOffsetHours, utcHourToLocal, renderTable, wordCloudHtml } =
  common;

describe("escapeHtml", () => {
  it("escapes the five HTML metacharacters", () => {
    expect(escapeHtml(`<a href="x">&'</a>`)).toBe(
      "&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;",
    );
  });

  it("coerces non-string input via String()", () => {
    expect(escapeHtml(42)).toBe("42");
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

describe("getTimezoneOffsetHours", () => {
  it("negates and divides Date#getTimezoneOffset by 60", () => {
    const date = { getTimezoneOffset: () => -330 }; // IST = UTC+5:30
    expect(getTimezoneOffsetHours(date)).toBe(5.5);
  });

  it("returns 0 for UTC", () => {
    // ``-0 / 60`` evaluates to ``-0``; ``toBeCloseTo`` ignores the sign.
    expect(getTimezoneOffsetHours({ getTimezoneOffset: () => 0 })).toBeCloseTo(0);
  });

  it("returns a negative offset for west-of-UTC timezones", () => {
    expect(getTimezoneOffsetHours({ getTimezoneOffset: () => 420 })).toBe(-7);
  });
});

describe("utcHourToLocal", () => {
  it("adds the offset and wraps modulo 24", () => {
    expect(utcHourToLocal(15, -7)).toBe(8);
    expect(utcHourToLocal(20, 5)).toBe(1);
    expect(utcHourToLocal(0, 0)).toBe(0);
  });

  it("wraps negative results back into 0-23", () => {
    expect(utcHourToLocal(2, -5)).toBe(21);
  });

  it("floors fractional offsets", () => {
    expect(utcHourToLocal(10, 5.5)).toBe(15);
  });
});

describe("renderTable", () => {
  const columns = [
    { header: "Name & Co", cell: (r) => escapeHtml(r.name) },
    { header: "Games", cell: (r) => fmt(r.count), cls: "num" },
  ];

  it("renders a no-data note when there are no rows", () => {
    expect(renderTable(columns, [])).toBe('<div class="no-data">No data yet.</div>');
  });

  it("escapes headers, right-aligns classed columns, and renders each cell", () => {
    const html = renderTable(columns, [{ name: "<b>", count: 1234 }]);
    expect(html).toBe(
      '<table class="lang-table"><thead><tr><th>Name &amp; Co</th>' +
        '<th style="text-align:right">Games</th></tr></thead><tbody>' +
        '<tr><td>&lt;b&gt;</td><td class="num">1,234</td></tr></tbody></table>',
    );
  });
});

describe("wordCloudHtml", () => {
  it("sizes words on a log scale and escapes phrases", () => {
    const html = wordCloudHtml(
      [
        { phrase: "no <proxies>", count: 1 },
        { phrase: "be nice", count: 100 },
      ],
      () => 0.5,
    );
    expect(html.startsWith('<div class="word-cloud">')).toBe(true);
    expect(html).toContain("font-size:0.8rem;color:#a78bfa;opacity:0.75;transform:rotate(0deg)");
    expect(html).toContain('title="1 games">no &lt;proxies&gt;</span>');
    expect(html).toContain("font-size:2rem;color:#60a5fa;opacity:1;");
  });

  it("handles a single phrase", () => {
    expect(wordCloudHtml([{ phrase: "solo", count: 3 }], () => 0.5)).toContain("solo");
  });
});
