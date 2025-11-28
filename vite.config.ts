import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react-swc";
import { defineConfig, PluginOption } from "vite";

import sparkPlugin from "@github/spark/spark-vite-plugin";
import createIconImportProxy from "@github/spark/vitePhosphorIconProxyPlugin";
import { resolve } from 'path'

const projectRoot = process.env.PROJECT_ROOT || import.meta.dirname;

// Centralized environment detection so Spark vs Codespaces vs Local do NOT require manual edits.
// Prefer controlling behavior via env vars instead of modifying this file:
// FRONTEND_PORT       -> overrides default port (5000)
// BACKEND_URL         -> proxy target (defaults to http://localhost:8000)
// HOST_BIND           -> explicit host binding (e.g. 0.0.0.0)
// DISABLE_STRICT_PORT -> set to "1" to allow fallback if port busy
// PUBLIC_PROXY_TIMEOUT_MS -> override proxy timeout (default 300000)
// Set HOST_BIND=0.0.0.0 in Codespaces or remote containers for browser tunnel & mobile devices.

const isCodespaces = !!process.env.CODESPACE_NAME;
const isSparkCI = !!process.env.SPARK_ENV; // heuristic – Spark may set its own env markers

const frontendPort = process.env.FRONTEND_PORT ? Number(process.env.FRONTEND_PORT) : 5000;
const hostBind = process.env.HOST_BIND || (isCodespaces ? '0.0.0.0' : 'localhost');
const strictPort = process.env.DISABLE_STRICT_PORT === '1' ? false : true;
const proxyTimeout = process.env.PUBLIC_PROXY_TIMEOUT_MS ? Number(process.env.PUBLIC_PROXY_TIMEOUT_MS) : 300000;
const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    createIconImportProxy() as PluginOption,
    sparkPlugin() as PluginOption,
  ],
  resolve: {
    alias: {
      '@': resolve(projectRoot, 'src')
    }
  },
  server: {
    port: frontendPort,
    host: hostBind,
    strictPort,
    hmr: {
      overlay: true,
      clientPort: frontendPort,
    },
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
        timeout: proxyTimeout,
        proxyTimeout,
      }
    }
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'react/jsx-runtime', 'react-router-dom'],
    exclude: ['@github/spark'],
  },
  esbuild: {
    logOverride: { 'this-is-undefined-in-esm': 'silent' }
  },
  build: {
    sourcemap: true,
    rollupOptions: {
      onwarn(warning, warn) {
        if (warning.code === 'MODULE_LEVEL_DIRECTIVE') return;
        warn(warning);
      }
    }
  }
});
