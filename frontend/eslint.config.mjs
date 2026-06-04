// next lint automatically applies eslint-config-next. This file only adds
// project-specific overrides — no need to import eslint-config-next here,
// which avoids plugin-scope incompatibilities with eslint-plugin-react on ESLint 10.

/** @type {import("eslint").Linter.Config[]} */
const config = [
  {
    rules: {
      "react/no-unescaped-entities": "off",
    },
  },
  {
    files: ["tests/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
    },
  },
  {
    ignores: ["node_modules/**", ".next/**", "out/**", "public/**", "coverage/**"],
  },
];

export default config;
