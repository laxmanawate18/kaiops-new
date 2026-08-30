import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Dev-proxy target is configurable — never hardcode an environment into the build.
  const proxyTarget = env.VITE_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [react()],
    resolve: {
      alias: { '@': path.resolve(__dirname, './src') },
    },
    server: {
      port: 5173,
      strictPort: false,
      proxy: {
        // Everything the app talks to lives under these prefixes.
        '/api': { target: proxyTarget, changeOrigin: true, secure: false },
        '/run': { target: proxyTarget, changeOrigin: true, secure: false },
        '/run_sse': { target: proxyTarget, changeOrigin: true, secure: false },
        '/list-apps': { target: proxyTarget, changeOrigin: true, secure: false },
        '/apps': { target: proxyTarget, changeOrigin: true, secure: false },
      },
    },
    build: {
      // Production source maps are an information disclosure; keep them out of the bundle.
      sourcemap: false,
      target: 'es2022',
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return
            const mod = id.split('node_modules/').pop() ?? ''

            // Heavy, lazily-reached libraries get their own chunks so they
            // never block first paint. three.js alone is ~840kb.
            if (/^(three|@react-three|three-mesh-bvh|troika)/.test(mod)) return 'three'
            if (/^(recharts|d3-|victory|internmap|delaunator|robust-predicates)/.test(mod)) return 'charts'
            if (/^(react-markdown|remark|rehype|hast|mdast|unified|micromark|vfile|bail|trough|character-entities|decode-named|property-information|space-separated|comma-separated|zwitch|longest-streak|html-void|ccount|markdown-table|escape-string-regexp|devlop|estree|unist)/.test(mod))
              return 'markdown'
            if (/^framer-motion/.test(mod)) return 'motion'
            // cmdk and Radix's scroll/focus helpers must share Radix's chunk —
            // cmdk imports @radix-ui/react-dialog, so splitting them creates a
            // radix -> vendor -> radix cycle.
            if (/^(@radix-ui|cmdk|aria-hidden|react-remove-scroll|react-style-singleton|use-callback-ref|use-sidecar|get-nonce|detect-node-es|tslib)/.test(mod))
              return 'radix'
            if (/^(react-hook-form|@hookform|zod)/.test(mod)) return 'forms'

            // Keep the React runtime itself in one leaf chunk. Anything that
            // *depends* on React (router, query, cmdk) must NOT live here, or
            // rollup produces a vendor -> react -> vendor cycle.
            if (/^(react|react-dom|scheduler)\//.test(mod) || /^(react|react-dom|scheduler)$/.test(mod))
              return 'react'

            return 'vendor'
          },
        },
      },
      chunkSizeWarningLimit: 900,
    },
  }
})
