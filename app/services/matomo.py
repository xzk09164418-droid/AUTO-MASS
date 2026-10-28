#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025-2026 AUTO-MAS Team

#   This file is part of AUTO-MAS.

#   AUTO-MAS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.

#   AUTO-MAS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
#   the GNU Affero General Public License for more details.

#   You should have received a copy of the GNU Affero General Public License
#   along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

#   Contact: DLmaster_361@163.com


class _MatomoHandler:
    """本机构建停用统计上报，保留异步接口供现有业务调用。

    不创建 HTTP/TLS 客户端，不把停用伪装成上传成功。本地任务日志、错误记录和
    通知不经过此接口，不受统计功能移除影响。
    """

    async def send_event(
        self, category, action, name=None, value=None, custom_vars=None
    ):
        return None

    async def close(self):
        return None


Matomo = _MatomoHandler()
