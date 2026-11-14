import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // static build in frontend/out, served by the Python engine for the desktop app
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
