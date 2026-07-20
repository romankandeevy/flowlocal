import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  basePath: "/flowlocal",
  assetPrefix: "/flowlocal/",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
