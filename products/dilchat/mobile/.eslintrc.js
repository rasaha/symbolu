module.exports = {
  extends: ["expo"],
  ignorePatterns: ["node_modules", ".expo", "scripts"],
  rules: {
    // Unused catch bindings are intentional in a few places (the handler inspects
    // other state, not the error object). Keep all other unused-var checks strict.
    "@typescript-eslint/no-unused-vars": [
      "warn",
      { args: "after-used", caughtErrors: "none", argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
    ],
  },
};
