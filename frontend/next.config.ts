// The browser calls /api/* and Next.js forwards requests to FastAPI.
import type { NextConfig } from "next";

const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8001";

const config: NextConfig = {
  rewrites: async () => [
    {
      source: "/api/:path*",
      destination: `${backend}/:path*`,
    },
  ],
  experimental: {
    proxyClientMaxBodySize: "16mb",
  },
};

export default config;

