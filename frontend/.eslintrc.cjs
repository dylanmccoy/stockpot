/* https://google.github.io/styleguide/tsguide.html
   ESLint config for the Google TypeScript Style Guide's enforceable rules.
   Prettier owns formatting; React Hooks adds framework-specific correctness. */
module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: "module",
    ecmaFeatures: { jsx: true },
    project: "./tsconfig.eslint.json",
    tsconfigRootDir: __dirname,
  },
  env: { browser: true, es2022: true, node: true },
  plugins: ["@typescript-eslint"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
  ],
  rules: {
    // Google TypeScript Style Guide: language and source-code rules.
    "block-scoped-var": "error",
    eqeqeq: "error",
    "no-debugger": "error",
    "no-eval": "error",
    "no-restricted-properties": [
      "error",
      { object: "describe", property: "only" },
      { object: "it", property: "only" },
      { object: "test", property: "only" },
    ],
    "no-var": "error",
    "prefer-arrow-callback": "error",
    "prefer-const": "error",

    // Google TypeScript Style Guide: type-system rules.
    "@typescript-eslint/array-type": ["error", { default: "array-simple" }],
    "@typescript-eslint/ban-ts-comment": [
      "error",
      {
        "ts-check": false,
        "ts-expect-error": true,
        "ts-ignore": true,
        "ts-nocheck": true,
      },
    ],
    "@typescript-eslint/consistent-type-imports": [
      "error",
      { prefer: "type-imports", fixStyle: "inline-type-imports" },
    ],
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/no-floating-promises": "error",
    "@typescript-eslint/no-namespace": "error",
    "@typescript-eslint/no-unused-vars": [
      "error",
      { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
    ],

    // TypeScript resolves identifiers; the base rule misreads type-only names.
    "no-undef": "off",
    "no-empty": ["error", { allowEmptyCatch: true }],
  },
  ignorePatterns: ["dist/", "node_modules/", "coverage/", "*.cjs"],
};
