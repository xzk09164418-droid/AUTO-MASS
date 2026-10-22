// 仅承载本机文件与界面配置，业务请求仍使用原有 Python API composables。
export async function invokeBrowserHost<T>(method: string, ...args: unknown[]): Promise<T> {
  const response = await fetch('/__host/invoke', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ method, args }),
  })
  const result = await response.json()
  if (!response.ok || !result.success) throw new Error(result.error || response.statusText)
  return result.data as T
}
