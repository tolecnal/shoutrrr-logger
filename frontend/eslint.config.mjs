import nextConfig from "eslint-config-next";

// `next lint` (which used to apply eslint-config-next automatically) was
// removed in Next.js 16 — see https://nextjs.org/docs/app/guides/upgrading/version-16.
// Running ESLint directly now, so the base config must be spread in here.

/** @type {import("eslint").Linter.Config[]} */
const config = [
  ...nextConfig,
  {
    rules: {
      "react/no-unescaped-entities": "off",
      // These React Compiler rules flag textbook-valid patterns used
      // throughout this codebase and vendored shadcn/ui components alike:
      // hydrating state from localStorage on mount (avoids SSR mismatch),
      // clamping pagination after a data change, syncing a media-query
      // listener, and generating a randomized skeleton width.
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/purity": "off",
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
