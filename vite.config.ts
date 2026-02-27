import tailwindcss from "@tailwindcss/vite";
import reactSwc from "@vitejs/plugin-react-swc";
import { defineConfig, PluginOption } from "vite";

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



const frontendPort = process.env.FRONTEND_PORT ? Number(process.env.FRONTEND_PORT) : (Number(process.env.PORT) || 5000);
const hostBind = process.env.HOST_BIND || '0.0.0.0';
const strictPort = process.env.DISABLE_STRICT_PORT === '1' ? false : true;
const proxyTimeout = process.env.PUBLIC_PROXY_TIMEOUT_MS ? Number(process.env.PUBLIC_PROXY_TIMEOUT_MS) : 300000;
const backendUrl = process.env.BACKEND_URL || 'http://localhost:8001';
// If hostBind is 0.0.0.0 and we're behind an HTTPS dev tunnel, forcing HMR host to 0.0.0.0 generates wss://0.0.0.0 which the browser rejects.
// Allow automatic fallback to window.location.hostname by omitting host when bound to 0.0.0.0 unless HMR_HOST is explicitly provided.



export default defineConfig({
  plugins: [
    reactSwc(),
    tailwindcss(),
  ],
  server: {
    port: frontendPort,
    host: hostBind,
    strictPort,
    allowedHosts: true,
    hmr: {
      overlay: true,
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
  resolve: {
    alias: {
      '@': resolve(projectRoot, 'src')
    }
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'react/jsx-runtime', 'react-router-dom'],
    force: false,
    esbuildOptions: {
      target: 'esnext'
    }
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
