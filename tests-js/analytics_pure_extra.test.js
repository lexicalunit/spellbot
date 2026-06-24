import { describe, it, expect } from "vitest";
import pure from "../src/spellbot/web/templates/analytics_pure.js";

const { escapeHtml, renderPlayerRow, renderLeftServerNote, getUserTimezone, getLanguageName } =
  pure;

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

describe("renderPlayerRow", () => {
  it("renders a plain row when the player is still on the server", () => {
    const html = renderPlayerRow({
      name: "Alice",
      user_xid: "12345",
      count: 1500,
      left_server: false,
    });
    expect(html).toBe(
      "<tr><td>Alice</td>" +
        '<td style="color:#9ca3af;font-size:0.8rem">12345</td>' +
        '<td class="count">1,500</td></tr>',
    );
  });

  it("adds the left-server badge and row class when the player has left", () => {
    const html = renderPlayerRow({
      name: "Bob",
      user_xid: "9",
      count: 1,
      left_server: true,
    });
    expect(html).toContain(' class="left-server"');
    expect(html).toContain('<span class="left-badge"');
  });

  it("HTML-escapes the player name", () => {
    const html = renderPlayerRow({
      name: "<script>",
      user_xid: "1",
      count: 1,
      left_server: false,
    });
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
  });
});

describe("renderLeftServerNote", () => {
  it("returns the explanation note when at least one player has left", () => {
    expect(renderLeftServerNote([{ left_server: false }, { left_server: true }])).toContain(
      "left-server-note",
    );
  });

  it("returns an empty string when nobody has left", () => {
    expect(renderLeftServerNote([{ left_server: false }])).toBe("");
    expect(renderLeftServerNote([])).toBe("");
  });
});

describe("getUserTimezone", () => {
  it("returns the abbreviation reported by Intl.DateTimeFormat", () => {
    // Node's ICU normally reports something like "GMT+5" or "UTC"; just
    // assert that we got a non-empty string back.
    const tz = getUserTimezone(new Date(Date.UTC(2026, 0, 1)));
    expect(typeof tz).toBe("string");
    expect(tz.length).toBeGreaterThan(0);
  });

  it("falls back to UTC±N when no timeZoneName part is produced", () => {
    const fake = {
      getTimezoneOffset: () => -120, // UTC+2
    };
    // Force the formatter path to throw so we hit the catch branch.
    const orig = global.Intl;
    global.Intl = {
      DateTimeFormat: function () {
        throw new Error("boom");
      },
    };
    try {
      expect(getUserTimezone(fake)).toBe("UTC+2");
    } finally {
      global.Intl = orig;
    }
  });

  it("uses a bare 'UTC' prefix for negative offsets", () => {
    const fake = { getTimezoneOffset: () => 420 }; // UTC-7
    const orig = global.Intl;
    global.Intl = {
      DateTimeFormat: function () {
        throw new Error("boom");
      },
    };
    try {
      expect(getUserTimezone(fake)).toBe("UTC-7");
    } finally {
      global.Intl = orig;
    }
  });
});

describe("getLanguageName", () => {
  const real = new Intl.DisplayNames(["en"], { type: "language" });

  it("returns the display name for a known locale", () => {
    expect(getLanguageName("en", real)).toBeTruthy();
  });

  it("falls back to the raw locale when the lookup returns falsy", () => {
    const stub = { of: () => "" };
    expect(getLanguageName("xx-YY", stub)).toBe("xx-YY");
  });

  it("returns the raw locale when the lookup throws", () => {
    const stub = {
      of: () => {
        throw new Error("nope");
      },
    };
    expect(getLanguageName("xx-YY", stub)).toBe("xx-YY");
  });
});
