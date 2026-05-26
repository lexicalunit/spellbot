import { describe, it, expect } from "vitest";
import pure from "../src/spellbot/web/templates/analytics_pure.js";

const {
  toDayMap,
  fmt,
  periodLabel,
  getTimezoneOffsetHours,
  utcHourToLocal,
  getTodayUTC,
  getTodayLocal,
  excludeToday,
} = pure;

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

describe("fmt", () => {
  it("formats numbers with grouping separators", () => {
    expect(fmt(0)).toBe("0");
    expect(fmt(1234567)).toBe("1,234,567");
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

describe("getTimezoneOffsetHours", () => {
  it("negates and divides Date#getTimezoneOffset by 60", () => {
    const date = { getTimezoneOffset: () => -330 }; // IST = UTC+5:30
    expect(getTimezoneOffsetHours(date)).toBe(5.5);
  });

  it("returns 0 for UTC", () => {
    // ``-0 / 60`` evaluates to ``-0``; ``toBeCloseTo`` ignores the sign.
    expect(getTimezoneOffsetHours({ getTimezoneOffset: () => 0 })).toBeCloseTo(
      0,
    );
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
    expect(
      excludeToday(
        ["2026-03-03", "2026-03-04", "2026-03-05", "2026-03-06"],
        fake,
      ),
    ).toEqual(["2026-03-03", "2026-03-06"]);
  });

  it("returns the original list when neither today value is present", () => {
    const fake = {
      toISOString: () => "2026-03-05T00:00:00.000Z",
      getFullYear: () => 2026,
      getMonth: () => 2,
      getDate: () => 5,
    };
    expect(excludeToday(["2026-03-01", "2026-03-02"], fake)).toEqual([
      "2026-03-01",
      "2026-03-02",
    ]);
  });
});
