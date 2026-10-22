import { defineConfig, mergeConfig } from 'vite-plus'
import baseConfig from '../vite.config'
import path from 'node:path'

export default defineConfig(async env => {
  const config = mergeConfig(await baseConfig(env), {
    build: {
      outDir: 'dist-browser',
      rollupOptions: { input: { main: path.resolve(__dirname, '../browser.html') } },
    },
  })
  config.build!.rollupOptions!.input = { main: path.resolve(__dirname, '../browser.html') }
  return config
})
