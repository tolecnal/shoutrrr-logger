import { readFileSync } from "fs";
import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin();

const { version } = JSON.parse(readFileSync(new URL("./package.json", import.meta.url)));

/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_APP_VERSION: version,
  },
  // Standalone output is required for the Docker image (copies only the files
  // needed to run, skipping node_modules not used at runtime).
  // Disabled in development so the v0 preview dev server works normally.
  ...(process.env.NODE_ENV === "production" ? { output: "standalone" } : {}),


  // Proxy /api/* → FastAPI backend.
  // In Docker the backend runs on port 9000 (set via BACKEND_URL env var).
  // In the v0 preview the backend service is discovered automatically.
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL ?? "http://localhost:9000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
