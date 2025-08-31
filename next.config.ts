import type { NextConfig } from "next";

const backend = process.env.NEXT_PUBLIC_BACKEND_URL;

const nextConfig: NextConfig = {
  async rewrites() {
    if (!backend) return [];
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },
  /* config options here */
};

export default nextConfig;
