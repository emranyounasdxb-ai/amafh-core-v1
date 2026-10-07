import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { defineConfig, loadEnv } from "vite";
import { securityHeaders } from "./securityHeaders.ts";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "AMAFH_DEV_");
  return {
    plugins: [react()],
    publicDir: "../assets/branding",
    server: {
      host: "localhost",
      strictPort: true,
      headers: securityHeaders(true),
      https:
        env.AMAFH_DEV_TLS_CERT && env.AMAFH_DEV_TLS_KEY
          ? {
              cert: readFileSync(env.AMAFH_DEV_TLS_CERT),
              key: readFileSync(env.AMAFH_DEV_TLS_KEY),
            }
          : undefined,
      proxy: env.AMAFH_DEV_API_TARGET
        ? {
            "/api/v1": {
              target: env.AMAFH_DEV_API_TARGET,
              changeOrigin: false,
            },
          }
        : undefined,
    },
    preview: { host: "localhost", strictPort: true, headers: securityHeaders(false) },
  };
});
