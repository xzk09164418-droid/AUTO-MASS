# 外部程序占用与邮箱控制

在“本机与热键 → 外部程序接口”查看当前后端地址、真实脚本 ID、字段说明和完整示例。
不要使用远程桌面宿主端口。直接 HTTP 调用仅限本机；远程电脑通过 QQ 邮箱发送签名指令。

## 两种借用机制

远程桌面借用沿用 `/api/child-session/acquire`（`/request` 为别名）、
`GET /api/child-session/status` 和 `/api/child-session/release`。
它等待当前子任务结束，在任务边界让渡整个桌面。取得 `granted` 后才能连接，结束后用 `leaseId` 释放。

脚本占用使用 `POST /api/dispatch/external-holds/acquire`、`release`、`status`。
它停止指定脚本当前的执行，完成进程清理后才进入 `active`；其他未占用项目继续运行。
`stopping` 只代表受理，不能开始使用项目。清理失败显示 `failed`，请检查错误并手动处理。
最后一个占用解除或到期后，脚本从头重跑，已完成步骤可能重复；原历史记录和计数保留。
队列只调整本次运行顺序，保存的顺序不变。多项目按完全释放的先后顺序恢复。
用户手动停止队列后不会因释放而重新启动。重启保留未到期占用，但不重启队列。

## 配置与签名

为每个外部程序保存独立 `callerId` 和至少 32 字符密钥。占用只按脚本 ID 判断，
不推断多个脚本是否指向同一程序路径；多个外部程序之间的互斥由它们自行协调。

JSON 命令含 `version=1`、唯一 `requestId`、`callerId`、`action`、规范 UUID `scriptId`、
`holdId`、带时区的 `issuedAt`。申请还必须提供 `ttlSeconds`（1–86400 秒）。
同一占用的三个动作使用相同 `holdId`；每个新动作使用新 `requestId`。

将 JSON 以 UTF-8 编码，再做不带 `=` 填充的 Base64URL 得到 `payload`；
对 `payload` 的 ASCII 原文使用调用方密钥计算 HMAC-SHA256 小写十六进制 `signature`。
HTTP 请求和邮件正文都只发送 `{"payload":"...","signature":"..."}`。
重复指令不延长占用；同一请求 ID 对应不同正文会被拒绝。释放先到达也会保留墓碑，迟到申请不会重新生效。
新指令签发时间最多早于当前 5 分钟、晚于当前 1 分钟；有效期从签发时间计算。

标准库示例：`scripts/external_control_client.py`。先在外部程序环境设置
`AUTO_MAS_CONTROL_SECRET`，不要把密钥写入日志或版本库。例如：

```text
python scripts/external_control_client.py acquire --caller worker1 --script <脚本UUID> --hold job-001 --ttl 1800 --transport http --base <页面显示的后端地址>
python scripts/external_control_client.py status --caller worker1 --script <脚本UUID> --hold job-001 --transport http --base <页面显示的后端地址>
python scripts/external_control_client.py release --caller worker1 --script <脚本UUID> --hold job-001 --transport http --base <页面显示的后端地址>
```

## QQ 邮箱

启用 QQ 邮箱的 IMAP/SMTP 服务，使用授权码而不是登录密码。在页面保存账号、授权码和调用方密钥，
测试连接后启用邮箱控制。IMAP 为 `imap.qq.com:993`，SMTP 为 `smtp.qq.com:465`，均验证 TLS 证书。

邮件由自己发给自己，标题严格为 `[AUTO-MAS COMMAND v1]`，正文为上述签名信封。
脚本示例使用 `--transport mail --account <自己的邮箱>`，授权码从 `AUTO_MAS_QQ_AUTH` 读取。
默认每 5 秒检查一次，网络失败退避重试。首次启用建立当前位置，不执行历史邮件；之后断线补收。
程序不删除邮件、不改变已读状态、不执行附件。

回执标题为 `[AUTO-MAS RECEIPT v1]`，发送到配置账号。只有 `active` 才表示可以使用；
回执发送失败会重试，不回滚已执行的指令。SMTP 在极端崩溃时可能重复发送回执，请按请求 ID 识别。
邮件网络延迟不属于本机接口响应时间。Server酱未接入本版本。

占用和游标保存在 `data/external-holds.sqlite3`，授权码和密钥以本机 DPAPI 加密；
备份时应包含该数据库。转移到其他电脑后需要重新填写秘密信息，不保证原密文可解密。
