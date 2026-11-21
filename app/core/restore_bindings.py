#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2025-2026 AUTO-MAS Team
#
#   This file is part of AUTO-MAS.
#
#   AUTO-MAS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License
#   as published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.
#
#   AUTO-MAS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

"""宿主内置恢复池装配：只保留通用脚本。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.config import GeneralConfig

if TYPE_CHECKING:
    from app.models.ConfigBase import ConfigBase
    from app.utils.config_restore import ConfigRestorePool


def resolve_restore_pools(script_config: ConfigBase) -> list[ConfigRestorePool]:
    """通用脚本使用自身的恢复池；其余专项已移除。"""

    if isinstance(script_config, GeneralConfig):
        from app.task.general.tools.restore_service import RESTORE_POOLS

        return RESTORE_POOLS
    raise ValueError("该专项暂不支持配置恢复")
