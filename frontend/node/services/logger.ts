// 纯 Node 服务的日志输出；原版业务服务保持原有日志调用方式。
export function getLogger(name: string) {
  return {
    debug: (...args: unknown[]) => console.debug(`[${name}]`, ...args),
    info: (...args: unknown[]) => console.info(`[${name}]`, ...args),
    warn: (...args: unknown[]) => console.warn(`[${name}]`, ...args),
    error: (...args: unknown[]) => console.error(`[${name}]`, ...args),
  }
}
