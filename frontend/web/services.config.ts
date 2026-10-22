import { defineConfig } from 'vite-plus'
import path from 'node:path'

export default defineConfig({
  plugins: [
    {
      name: 'no-electron-runtime',
      resolveId(id, importer) {
        if (id === './logger' && importer?.replaceAll('\\', '/').includes('/electron/services/'))
          return path.resolve(__dirname, 'logger.ts')
        if (id === 'electron' || id.startsWith('@sentry/electron'))
          throw new Error(`浏览器宿主禁止导入 ${id}`)
      },
    },
  ],
  build: {
    ssr: true,
    target: 'node22',
    outDir: 'dist-host',
    lib: {
      entry: path.resolve(__dirname, 'services.ts'),
      formats: ['cjs'],
      fileName: () => 'services.cjs',
    },
    rollupOptions: {
      external: [/^node:/, 'fs', 'path', 'child_process', 'util', 'crypto', 'os', 'adm-zip'],
      output: { format: 'cjs', entryFileNames: 'services.cjs' },
    },
  },
})
