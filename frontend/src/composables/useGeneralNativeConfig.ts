import { Service, type GeneralNativeConfigOut } from '@/api'

export function useGeneralNativeConfig() {
  const check = (result: GeneralNativeConfigOut) => {
    if (result.code !== 200) throw new Error(result.message || '原生配置操作失败')
    return result
  }
  return {
    read: async (scriptId: string, file = '') =>
      check(
        await Service.readGeneralNativeConfigApiScriptsGeneralNativeReadPost({ scriptId, file })
      ),
    write: async (scriptId: string, file: string, content: string, revision: string) =>
      check(
        await Service.writeGeneralNativeConfigApiScriptsGeneralNativeWritePost({
          scriptId,
          file,
          content,
          revision,
        })
      ),
  }
}
