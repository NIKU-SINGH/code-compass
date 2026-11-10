import type { NextConfig } from "next";

// `STATIC_EXPORT=1 pnpm build` writes plain HTML/JS to `out/`, which `make web-static`
// copies into compass_server so an installed `compass serve` can serve the UI itself.
// The dev server instead proxies `/api` to the FastAPI server.
const staticExport = process.env.STATIC_EXPORT === "1";

const nextConfig: NextConfig = staticExport
  ? { output: "export" }
  : {
      async rewrites() {
        return [
          {
            source: "/api/:path*",
            destination: `${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/api/:path*`,
          },
        ];
      },
    };

export default nextConfig;
