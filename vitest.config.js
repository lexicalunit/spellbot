// Vitest configuration for the pure helpers in src/spellbot/web/templates.
// The tests load each *_pure.js as a CommonJS module via the trailing
// module.exports block that those files include for non-browser environments.

module.exports = {
  test: {
    include: ["tests-js/**/*.test.js"],
    environment: "node",
    coverage: {
      provider: "v8",
      include: ["src/spellbot/web/templates/*_pure.js"],
      reporter: ["text", "html"],
    },
  },
};
