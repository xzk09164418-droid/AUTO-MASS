/** 可复制示例的唯一前端来源。仅生成文本，不读取密钥、不发送请求。 */
export function externalControlExamples(
  base: string,
  scriptId: string,
  callerId: string,
  holdId: string
) {
  const command = {
    version: 1,
    requestId: 'REPLACE_WITH_UNIQUE_REQUEST_ID',
    callerId,
    action: 'acquire',
    scriptId,
    holdId,
    issuedAt: new Date().toISOString(),
    ttlSeconds: 1800,
  }
  const url = `${base.replace(/\/$/, '')}/api/dispatch/external-holds`
  const python = `import base64, hashlib, hmac, json, os, uuid, urllib.request
from datetime import datetime, timezone

# 密钥由外部程序的环境变量提供，不要把密钥写入邮件模板或日志。
command = json.loads(${JSON.stringify(JSON.stringify(command))})
command['requestId'] = str(uuid.uuid4())
command['issuedAt'] = datetime.now(timezone.utc).isoformat()
# 释放/查询时 action 改为 release/status，并保留 callerId、scriptId、holdId。
payload = base64.urlsafe_b64encode(json.dumps(command, ensure_ascii=False).encode()).decode().rstrip('=')
envelope = {'payload': payload, 'signature': hmac.new(os.environ['AUTO_MAS_CONTROL_SECRET'].encode(), payload.encode('ascii'), hashlib.sha256).hexdigest()}
body = json.dumps(envelope).encode()
# 邮箱通道：标题 [AUTO-MAS COMMAND v1]，正文使用 body.decode()，发给自己。
# 本机 HTTP 调用：
request = urllib.request.Request(${JSON.stringify(url)} + '/' + command['action'], data=body, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(request, timeout=10) as response:
    print(response.read().decode())
# acquire 返回 stopping 时，用新的 requestId 发送 status，直到 state=active。
`
  return {
    url,
    command: JSON.stringify(command, null, 2),
    python,
    envelope: JSON.stringify(
      { payload: '<BASE64URL_UTF8_JSON>', signature: '<HMAC_SHA256_HEX>' },
      null,
      2
    ),
    curl: `curl "${url}/acquire" -H "Content-Type: application/json" --data-binary @envelope.json`,
    desktopAcquire: JSON.stringify(
      {
        caller: callerId,
        disconnectRdpView: true,
        timeoutSeconds: 3600,
        waitForGrant: false,
        waitTimeout: 300,
      },
      null,
      2
    ),
    desktopRelease: JSON.stringify({ leaseId: '<申请返回的 leaseId>' }, null, 2),
  }
}
