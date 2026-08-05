// Babel config for the Node integration harness only. Strips TypeScript types
// and rewrites ESM imports to CommonJS so the PRODUCTION api/ modules run
// unchanged under Node's real `fetch` (no React Native / Expo runtime).
module.exports = {
  presets: [["@babel/preset-typescript", { onlyRemoveTypeImports: true }]],
  plugins: ["@babel/plugin-transform-modules-commonjs"],
};
