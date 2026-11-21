import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    const none = [{ key: "Cache-Control", value: "no-store" }];
    const immutable = [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }];
    return [
      { source: "/", headers: none },
      { source: "/guide", headers: none },
      { source: "/m/:path*", headers: none },
      { source: "/s/:path*", headers: none },
      { source: "/a/:path*", headers: none },
      { source: "/sw.js", headers: none },
      {
        source: "/manifest.json",
        headers: [...none, { key: "Content-Type", value: "application/manifest+json" }],
      },
      ...["/favicon.png", "/icon-192.png", "/icon-512.png", "/wide.png"].map((source) => ({
        source,
        headers: immutable,
      })),
    ];
  },
};

export default nextConfig;
