import { describe, it, expect } from "vitest";
import pure from "../src/spellbot/web/templates/dashboard_pure.js";

const {
  PERIOD_BUCKET,
  PERIOD_DAYS,
  currentBucket,
  periodStartMs,
  bucketStartUtc,
  bucketEndUtc,
  computeTrim,
} = pure;

const DAY_MS = 24 * 60 * 60 * 1000;

describe("PERIOD_BUCKET / PERIOD_DAYS", () => {
  it("keeps day/week/month buckets in sync with dashboard_filters.py", () => {
    expect(PERIOD_BUCKET).toEqual({
      "7d": "day",
      "30d": "day",
      "90d": "day",
      "180d": "week",
      "365d": "week",
      "730d": "month",
      all: "month",
    });
    expect(PERIOD_DAYS).toEqual({
      "7d": 7,
      "30d": 30,
      "90d": 90,
      "180d": 180,
      "365d": 365,
      "730d": 730,
    });
  });
});

describe("currentBucket", () => {
  it("returns the configured bucket for known periods", () => {
    expect(currentBucket("7d")).toBe("day");
    expect(currentBucket("180d")).toBe("week");
    expect(currentBucket("730d")).toBe("month");
    expect(currentBucket("all")).toBe("month");
  });

  it("falls back to day for unknown periods", () => {
    expect(currentBucket("nonsense")).toBe("day");
  });
});

describe("periodStartMs", () => {
  const now = Date.UTC(2026, 0, 15);

  it("returns null for the all-time window", () => {
    expect(periodStartMs("all", now)).toBeNull();
  });

  it("returns null for unknown periods", () => {
    expect(periodStartMs("nonsense", now)).toBeNull();
  });

  it("subtracts the configured day count for known periods", () => {
    expect(periodStartMs("7d", now)).toBe(now - 7 * DAY_MS);
    expect(periodStartMs("30d", now)).toBe(now - 30 * DAY_MS);
    expect(periodStartMs("730d", now)).toBe(now - 730 * DAY_MS);
  });
});

describe("bucketStartUtc / bucketEndUtc", () => {
  it("parses YYYY-MM-DD as UTC midnight", () => {
    const start = bucketStartUtc("2026-03-15");
    expect(start.toISOString()).toBe("2026-03-15T00:00:00.000Z");
  });

  it("ignores trailing time portions on the input", () => {
    const start = bucketStartUtc("2026-03-15T13:45:00Z");
    expect(start.toISOString()).toBe("2026-03-15T00:00:00.000Z");
  });

  it("rolls forward by one day, week, or month in UTC", () => {
    const start = bucketStartUtc("2026-03-15");
    expect(bucketEndUtc(start, "day").toISOString()).toBe(
      "2026-03-16T00:00:00.000Z",
    );
    expect(bucketEndUtc(start, "week").toISOString()).toBe(
      "2026-03-22T00:00:00.000Z",
    );
    expect(bucketEndUtc(start, "month").toISOString()).toBe(
      "2026-04-15T00:00:00.000Z",
    );
  });

  it("defaults to day when bucket is unrecognized", () => {
    const start = bucketStartUtc("2026-03-15");
    expect(bucketEndUtc(start, "decade").toISOString()).toBe(
      "2026-03-16T00:00:00.000Z",
    );
  });
});

describe("computeTrim", () => {
  const days = [
    "2026-03-10",
    "2026-03-11",
    "2026-03-12",
    "2026-03-13",
    "2026-03-14",
  ];

  it("starts at index 0 when startMs is null (all-time)", () => {
    const now = Date.UTC(2026, 2, 14, 12);
    const out = computeTrim(days, "day", now, null);
    expect(out.startIdx).toBe(0);
    expect(out.partialFromIdx).toBe(4);
  });

  it("trims leading buckets that begin before startMs", () => {
    const now = Date.UTC(2026, 2, 14, 12);
    const startMs = Date.UTC(2026, 2, 12);
    const out = computeTrim(days, "day", now, startMs);
    expect(out.startIdx).toBe(2);
    expect(out.partialFromIdx).toBe(2);
  });

  it("marks trailing partial buckets when their end is past now", () => {
    const now = Date.UTC(2026, 2, 12, 12);
    const out = computeTrim(days, "day", now, null);
    expect(out.startIdx).toBe(0);
    expect(out.partialFromIdx).toBe(2);
  });

  it("returns partialFromIdx equal to length when nothing trails", () => {
    const now = Date.UTC(2030, 0, 1);
    const out = computeTrim(days, "day", now, null);
    expect(out.partialFromIdx).toBe(days.length);
  });

  it("handles empty input", () => {
    const out = computeTrim([], "day", Date.UTC(2026, 0, 1), null);
    expect(out).toEqual({ startIdx: 0, partialFromIdx: 0 });
  });
});
