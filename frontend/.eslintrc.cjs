/* ESLint config (flat config not used — keeps the dep set to the spec §1 list).
   Formatting is Prettier's job; these rules are correctness-only so the two
   never conflict. */
module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  env: { browser: true, es2022: true, node: true },
  plugins: ["@typescript-eslint"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
  ],
  rules: {
    // TypeScript already resolves identifiers; `no-undef` only produces
    // false positives on type-only names (per typescript-eslint guidance).
    "no-undef": "off",
    "no-empty": ["error", { allowEmptyCatch: true }],
    "@typescript-eslint/no-unused-vars": [
      "error",
      { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
    ],
  },
  ignorePatterns: ["dist/", "node_modules/", "coverage/", "*.cjs"],
};
