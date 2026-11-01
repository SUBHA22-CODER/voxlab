import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep Turbopack's workspace root at the frontend dir — a stray
  // package-lock.json in a parent folder would otherwise be picked up.
  turbopack: {
    root: process.cwd(),
  },
};

export default nextConfig;
