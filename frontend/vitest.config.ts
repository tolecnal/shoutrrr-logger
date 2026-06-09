import { readFileSync } from "fs";
import path from "path";
import { defineConfig } from "vitest/config";

const { version } = JSON.parse(readFileSync("./package.json", "utf-8"));

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    env: {
      NEXT_PUBLIC_APP_VERSION: version,
    },
    include: ["tests/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["lib/**/*.ts", "lib/**/*.tsx"],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
