import type { NextConfig } from "next";

const config: NextConfig = {
  distDir: process.env.FORGE_DIST_DIR || ".next",
  poweredByHeader: false,
  devIndicators: false,
  logging: { incomingRequests: { ignore: [/\/api\/v1\/auth\/oauth\/[^/]+\/callback/] } },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.FORGE_API_URL || "http://127.0.0.1:8010"}/api/:path*` }];
  },
};
export default config;
