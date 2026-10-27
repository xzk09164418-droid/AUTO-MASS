"""通用脚本原生配置编辑接口。"""

import asyncio
import uuid

from fastapi import APIRouter

from app.core import Config
from app.models.config import GeneralConfig
from app.models.schema import (
    GeneralNativeConfigOut,
    GeneralNativeConfigReadIn,
    GeneralNativeConfigWriteIn,
)
from app.task.general.tools import native_config
from app.utils import get_logger

router = APIRouter()
logger = get_logger("通用原生配置")


@router.post("/general/native/read", response_model=GeneralNativeConfigOut)
async def read_general_native_config(
    request: GeneralNativeConfigReadIn,
) -> GeneralNativeConfigOut:
    try:
        script = Config.ScriptConfig[uuid.UUID(request.scriptId)]
        if not isinstance(script, GeneralConfig):
            raise ValueError("只支持通用脚本")
        if script.is_locked:
            raise ValueError("脚本正在运行，请结束任务后编辑")
        data = await asyncio.to_thread(native_config.read_config, script, request.file)
        return GeneralNativeConfigOut(**data)
    except Exception as error:
        logger.opt(exception=True).warning(f"读取原生配置失败: {error}")
        return GeneralNativeConfigOut(
            code=400 if isinstance(error, (ValueError, KeyError, TypeError)) else 500,
            status="error",
            message=str(error),
        )


@router.post("/general/native/write", response_model=GeneralNativeConfigOut)
async def write_general_native_config(
    request: GeneralNativeConfigWriteIn,
) -> GeneralNativeConfigOut:
    script = None
    locked = False
    try:
        script = Config.ScriptConfig[uuid.UUID(request.scriptId)]
        if not isinstance(script, GeneralConfig):
            raise ValueError("只支持通用脚本")
        if script.is_locked:
            raise ValueError("脚本正在运行，请结束任务后保存")
        await script.lock()
        locked = True
        operation = asyncio.create_task(
            asyncio.to_thread(
                native_config.write_config,
                request.scriptId,
                script,
                request.file,
                request.content,
                request.revision,
            )
        )
        try:
            data = await asyncio.shield(operation)
        except asyncio.CancelledError:
            # 线程中的落盘不能取消，保持脚本锁直到写入完成。
            await operation
            raise
        logger.info(f"原生配置已保存: {request.scriptId} {data['file']}")
        return GeneralNativeConfigOut(**data)
    except Exception as error:
        logger.opt(exception=True).warning(f"保存原生配置失败: {error}")
        return GeneralNativeConfigOut(
            code=400 if isinstance(error, (ValueError, KeyError, TypeError)) else 500,
            status="error",
            message=str(error),
        )
    finally:
        if locked and script is not None:
            await script.unlock()
