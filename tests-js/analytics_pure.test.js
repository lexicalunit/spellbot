import { describe, it, expect } from "vitest";
import pure from "../src/spellbot/web/templates/analytics_pure.js";

const { toDayMap, periodLabel, getTodayUTC, getTodayLocal, excludeToday } = pure;

describe("toDayMap", () => {
  it("indexes count by day", () => {
    expect(
      toDayMap([
        { day: "2026-01-01", count: 3 },
        { day: "2026-01-02", count: 7 },
      ]),
    ).toEqual({ "2026-01-01": 3, "2026-01-02": 7 });
  });

  it("returns an empty object for empty input", () => {
    expect(toDayMap([])).toEqual({});
  });
});

describe("periodLabel", () => {
  it("returns All Time for all", () => {
    expect(periodLabel("all")).toBe("All Time");
  });

  it("returns Last 30 Days for anything else", () => {
    expect(periodLabel("30d")).toBe("Last 30 Days");
    expect(periodLabel(undefined)).toBe("Last 30 Days");
  });
});

describe("getTodayUTC", () => {
  it("returns the UTC date as YYYY-MM-DD", () => {
    const d = new Date(Date.UTC(2026, 2, 5, 23, 59));
    expect(getTodayUTC(d)).toBe("2026-03-05");
  });
});

describe("getTodayLocal", () => {
  it("returns the date's local YYYY-MM-DD", () => {
    // construct a date via component-getters that simulate the local view
    const fake = {
      getFullYear: () => 2026,
      getMonth: () => 0, // January
      getDate: () => 3,
    };
    expect(getTodayLocal(fake)).toBe("2026-01-03");
  });
});

describe("excludeToday", () => {
  it("drops the UTC and local today entries", () => {
    const fake = {
      toISOString: () => "2026-03-05T00:30:00.000Z",
      getFullYear: () => 2026,
      getMonth: () => 2,
      getDate: () => 4,
    };
    expect(excludeToday(["2026-03-03", "2026-03-04", "2026-03-05", "2026-03-06"], fake)).toEqual([
      "2026-03-03",
      "2026-03-06",
    ]);
  });

  it("returns the original list when neither today value is present", () => {
    const fake = {
      toISOString: () => "2026-03-05T00:00:00.000Z",
      getFullYear: () => 2026,
      getMonth: () => 2,
      getDate: () => 5,
    };
    expect(excludeToday(["2026-03-01", "2026-03-02"], fake)).toEqual(["2026-03-01", "2026-03-02"]);
  });
});
