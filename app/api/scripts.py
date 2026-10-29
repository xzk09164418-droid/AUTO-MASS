#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025 MoeSnowyFox
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


import uuid

from fastapi import APIRouter, Body

from app.api.general_config import router as general_config_router
from app.core import Config
from app.core.game_calendar import SCRIPT_CALENDAR_GAMES
from app.models.schema import *
from app.services import ConfigCenterError
from app.utils import get_logger
from app.utils.emulator2 import service as emulator2_service
from app.utils.io import ConfigCorruptedError

router = APIRouter(prefix="/api/scripts", tags=["脚本管理"])
router.include_router(general_config_router)
logger = get_logger("脚本管理 API")


SCRIPT_BOOK = {"GeneralConfig": GeneralConfig}
USER_BOOK = {"GeneralConfig": GeneralUserConfig}


@router.get(
    "/ownership/prompts",
    response_model=GeneralOwnershipPromptsOut,
    tags=["GeneralOwnership"],
)
async def get_ownership_prompts() -> GeneralOwnershipPromptsOut:
    from app.core.general_ownership import general_ownership

    return GeneralOwnershipPromptsOut(data=general_ownership.prompts())


@router.post("/ownership/answer", response_model=OutBase, tags=["GeneralOwnership"])
async def answer_ownership_prompt(data: GeneralOwnershipAnswerIn) -> OutBase:
    from app.core.general_ownership import general_ownership

    if not general_ownership.respond(data.requestId, edit=data.edit):
        return OutBase(code=409, status="error", message="该提示已结束，请刷新状态")
    return OutBase()


@router.post(
    "/add",
    tags=["Add"],
    summary="添加脚本",
    response_model=ScriptCreateOut,
    status_code=200,
)
async def add_script(script: ScriptCreateIn = Body(...)) -> ScriptCreateOut:

    try:
        uid, config = await Config.add_script(script.type, script.scriptId)
        data = SCRIPT_BOOK[type(config).__name__](**(await config.toDict()))
    except Exception as e:
        logger.opt(exception=True).warning(f"add_script失败: {type(e).__name__}: {e}")
        return ScriptCreateOut(
            code=500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            scriptId="",
            data=GeneralConfig(**{}),
        )
    return ScriptCreateOut(scriptId=str(uid), data=data)


@router.post(
    "/get",
    tags=["Get"],
    summary="查询脚本配置信息",
    response_model=ScriptGetOut,
    status_code=200,
)
async def get_script(script: ScriptGetIn = Body(...)) -> ScriptGetOut:

    try:
        index, data = await Config.get_script(script.scriptId)
        activity_games = {
            config.__name__: game for config, game in SCRIPT_CALENDAR_GAMES.items()
        }
        index = [
            ScriptIndexItem(**item, activityGame=activity_games.get(item["type"]))
            for item in index
        ]
        data = {
            uid: SCRIPT_BOOK[next((_.type for _ in index if _.uid == uid), "General")](
                **cfg
            )
            for uid, cfg in data.items()
        }
    except Exception as e:
        logger.opt(exception=True).warning(f"get_script失败: {type(e).__name__}: {e}")
        return ScriptGetOut(
            code=500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            index=[],
            data={},
        )
    users = (
        {item.uid: await _get_user_response(item.uid) for item in index}
        if script.includeUsers
        else None
    )
    return ScriptGetOut(index=index, data=data, users=users)


@router.post(
    "/update",
    tags=["Update"],
    summary="更新脚本配置信息",
    response_model=OutBase,
    status_code=200,
)
async def update_script(script: ScriptUpdateIn = Body(...)) -> OutBase:

    try:
        data = script.data.model_dump(exclude_unset=True)
        # 魔改 AVD 目前只支持 MaaFW 和 MAA：别的脚本选魔改 AVD 设备，保存时就拦下
        refusal = await emulator2_service.mod_avd_binding_error(script.scriptId, data)
        if refusal:
            return OutBase(code=500, status="error", message=refusal)
        await Config.update_script(script.scriptId, data)
    except Exception as e:
        logger.opt(exception=True).warning(
            f"update_script失败: {type(e).__name__}: {e}"
        )
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()


@router.post(
    "/delete",
    tags=["Delete"],
    summary="删除脚本",
    response_model=OutBase,
    status_code=200,
)
async def delete_script(script: ScriptDeleteIn = Body(...)) -> OutBase:

    try:
        await Config.del_script(script.scriptId)
    except Exception as e:
        logger.opt(exception=True).warning(
            f"delete_script失败: {type(e).__name__}: {e}"
        )
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()


@router.post(
    "/order",
    tags=["Update"],
    summary="重新排序脚本",
    response_model=OutBase,
    status_code=200,
)
async def reorder_script(script: ScriptReorderIn = Body(...)) -> OutBase:

    try:
        await Config.reorder_script(script.indexList)
    except Exception as e:
        logger.opt(exception=True).warning(
            f"reorder_script失败: {type(e).__name__}: {e}"
        )
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()


@router.post(
    "/import/web",
    tags=["Update"],
    summary="从配置中心导入脚本配置",
    response_model=OutBase,
    status_code=200,
)
async def import_script_from_web(script: ScriptTemplateImportIn = Body(...)) -> OutBase:

    try:
        await Config.import_script_from_share(
            script.scriptId, config_key=script.configKey, version_no=script.versionNo
        )
    except ConfigCenterError as e:
        return OutBase(code=500, status="error", message=str(e))
    except Exception as e:
        logger.opt(exception=True).warning(
            f"import_script_from_web失败: {type(e).__name__}: {e}"
        )
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()


@router.post(
    "/share/inspect",
    tags=["Get"],
    summary="分享前检查脚本配置中的隐私风险",
    response_model=ShareInspectOut,
    status_code=200,
)
async def inspect_script_share(
    script: ScriptShareInspectIn = Body(...),
) -> ShareInspectOut:

    try:
        _, risks = await Config.build_share_config(
            script.scriptId, config_name=script.config_name
        )
    except Exception as e:
        return ShareInspectOut(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return ShareInspectOut(risks=[ShareRiskItem(**_) for _ in risks])


@router.post(
    "/Upload/web",
    tags=["Action"],
    summary="分享脚本配置到配置中心",
    response_model=OutBase,
    status_code=200,
)
async def upload_script_to_web(script: ScriptUploadIn = Body(...)) -> OutBase:

    try:
        await Config.upload_script_to_share(
            script.scriptId,
            config_name=script.config_name,
            description=script.description,
            acknowledged=script.acknowledged,
        )
    except ConfigCenterError as e:
        return OutBase(code=500, status="error", message=str(e))
    except Exception as e:
        logger.opt(exception=True).warning(
            f"upload_script_to_web失败: {type(e).__name__}: {e}"
        )
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()


@router.post(
    "/config/import",
    tags=["Action"],
    summary="从脚本目录导入配置文件",
    response_model=OutBase,
    status_code=200,
)
async def import_script_config_file(
    config: ScriptConfigImportIn = Body(...),
) -> OutBase:

    try:
        await Config.import_script_config_file(config.scriptId, config.userId)
    except Exception as e:
        logger.opt(exception=True).warning(
            f"import_script_config_file失败: {type(e).__name__}: {e}"
        )
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase(message="脚本配置文件已导入")


@router.post(
    "/user/get",
    tags=["Get"],
    summary="查询用户",
    response_model=UserGetOut,
    status_code=200,
)
async def get_user(user: UserGetIn = Body(...)) -> UserGetOut:
    return await _get_user_response(user.scriptId, user.userId)


async def _get_user_response(script_id: str, user_id: str | None = None) -> UserGetOut:
    """共用单脚本与列表合并读取的用户序列化和错误契约。"""

    try:
        index, data = await Config.get_user(script_id, user_id)
        index = [UserIndexItem(**_) for _ in index]
        data = {
            uid: USER_BOOK[type(Config.ScriptConfig[uuid.UUID(script_id)]).__name__](
                **cfg
            )
            for uid, cfg in data.items()
        }
    except Exception as e:
        logger.opt(exception=True).warning(f"get_user失败: {type(e).__name__}: {e}")
        return UserGetOut(
            code=500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            index=[],
            data={},
        )
    return UserGetOut(index=index, data=data)


@router.post(
    "/user/config-dir",
    tags=["Get"],
    summary="获取用户配置目录",
    response_model=UserConfigDirOut,
    status_code=200,
)
async def get_user_config_dir(user: UserConfigDirIn = Body(...)) -> UserConfigDirOut:

    try:
        user_config_dir = await Config.get_user_config_dir(user.scriptId, user.userId)
    except Exception as e:
        logger.opt(exception=True).warning(
            f"get_user_config_dir失败: {type(e).__name__}: {e}"
        )
        return UserConfigDirOut(
            code=500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            path="",
        )
    return UserConfigDirOut(message="用户配置目录获取成功", path=str(user_config_dir))


@router.post(
    "/user/add",
    tags=["Add"],
    summary="添加用户",
    response_model=UserCreateOut,
    status_code=200,
)
async def add_user(user: UserInBase = Body(...)) -> UserCreateOut:

    try:
        uid, config = await Config.add_user(user.scriptId)
        data = USER_BOOK[type(Config.ScriptConfig[uuid.UUID(user.scriptId)]).__name__](
            **(await config.toDict())
        )
    except FileNotFoundError as e:
        return UserCreateOut(
            code=409,
            status="error",
            message=str(e),
            userId="",
            data=GeneralUserConfig(**{}),
        )
    except Exception as e:
        logger.opt(exception=True).warning(f"add_user失败: {type(e).__name__}: {e}")
        return UserCreateOut(
            code=500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            userId="",
            data=GeneralUserConfig(**{}),
        )
    return UserCreateOut(userId=str(uid), data=data)


@router.post(
    "/user/update",
    tags=["Update"],
    summary="更新用户配置信息",
    response_model=OutBase,
    status_code=200,
)
async def update_user(user: UserUpdateIn = Body(...)) -> OutBase:
    data = user.data.model_dump(exclude_unset=True)

    try:
        await Config.update_user(user.scriptId, user.userId, data)
    except Exception as e:
        logger.opt(exception=True).warning(f"update_user失败: {type(e).__name__}: {e}")
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()


@router.post(
    "/user/delete",
    tags=["Delete"],
    summary="删除用户",
    response_model=OutBase,
    status_code=200,
)
async def delete_user(user: UserDeleteIn = Body(...)) -> OutBase:

    try:
        await Config.del_user(user.scriptId, user.userId)
    except Exception as e:
        logger.opt(exception=True).warning(f"delete_user失败: {type(e).__name__}: {e}")
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()


@router.post(
    "/user/order",
    tags=["Update"],
    summary="重新排序用户",
    response_model=OutBase,
    status_code=200,
)
async def reorder_user(user: UserReorderIn = Body(...)) -> OutBase:

    try:
        await Config.reorder_user(user.scriptId, user.indexList)
    except Exception as e:
        logger.opt(exception=True).warning(f"reorder_user失败: {type(e).__name__}: {e}")
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()


@router.post(
    "/webhook/get",
    tags=["Get"],
    summary="查询 webhook 配置",
    response_model=WebhookGetOut,
    status_code=200,
)
async def get_webhook(webhook: WebhookGetIn = Body(...)) -> WebhookGetOut:

    try:
        index, data = await Config.get_webhook(
            webhook.scriptId, webhook.userId, webhook.webhookId
        )
        index = [WebhookIndexItem(**_) for _ in index]
        data = {uid: Webhook(**cfg) for uid, cfg in data.items()}
    except Exception as e:
        logger.opt(exception=True).warning(f"get_webhook失败: {type(e).__name__}: {e}")
        return WebhookGetOut(
            code=500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            index=[],
            data={},
        )
    return WebhookGetOut(index=index, data=data)


@router.post(
    "/webhook/add",
    tags=["Add"],
    summary="添加webhook项",
    response_model=WebhookCreateOut,
    status_code=200,
)
async def add_webhook(webhook: WebhookInBase = Body(...)) -> WebhookCreateOut:

    try:
        uid, config = await Config.add_webhook(webhook.scriptId, webhook.userId)
        data = Webhook(**(await config.toDict()))
    except Exception as e:
        logger.opt(exception=True).warning(f"add_webhook失败: {type(e).__name__}: {e}")
        return WebhookCreateOut(
            code=500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            webhookId="",
            data=Webhook(**{}),
        )
    return WebhookCreateOut(webhookId=str(uid), data=data)


@router.post(
    "/webhook/update",
    tags=["Update"],
    summary="更新webhook项",
    response_model=OutBase,
    status_code=200,
)
async def update_webhook(webhook: WebhookUpdateIn = Body(...)) -> OutBase:

    try:
        await Config.update_webhook(
            webhook.scriptId,
            webhook.userId,
            webhook.webhookId,
            webhook.data.model_dump(exclude_unset=True),
        )
    except Exception as e:
        logger.opt(exception=True).warning(
            f"update_webhook失败: {type(e).__name__}: {e}"
        )
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()


@router.post(
    "/webhook/delete",
    tags=["Delete"],
    summary="删除webhook项",
    response_model=OutBase,
    status_code=200,
)
async def delete_webhook(webhook: WebhookDeleteIn = Body(...)) -> OutBase:

    try:
        await Config.del_webhook(webhook.scriptId, webhook.userId, webhook.webhookId)
    except Exception as e:
        logger.opt(exception=True).warning(
            f"delete_webhook失败: {type(e).__name__}: {e}"
        )
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()


@router.get(
    "/backup/list",
    tags=["Backup"],
    summary="列出配置备份（时间倒序；target 取值由专项定义，非法值返回 400）",
    response_model=ConfigBackupListOut,
    status_code=200,
)
async def list_config_backups_api(
    scriptId: str, userId: str, target: str
) -> ConfigBackupListOut:
    """返回 ``items``（``time`` + 备份时点来源标注 ``base``，倒序）与当前
    来源 ``base``（仅三态池，供前端跨来源提示）；非法 target 返回 400。"""

    try:
        data = await Config.list_config_backups(scriptId, userId, target)
        return ConfigBackupListOut(
            code=200,
            status="success",
            message=f"共 {len(data['items'])} 份备份",
            base=data["base"],
            data=[ConfigBackupItemOut(**item) for item in data["items"]],
        )
    except Exception as e:
        logger.opt(exception=True).warning(f"配置备份列表查询失败: {e}")
        return ConfigBackupListOut(
            code=400 if isinstance(e, (ValueError, KeyError, TypeError)) else 500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            data=[],
        )


@router.post(
    "/backup/ensure",
    tags=["Backup"],
    summary="按需归档目标池当前配置（指纹去重，无变化跳过；编辑界面进入/退出时机调用）",
    response_model=ConfigBackupEnsureOut,
    status_code=200,
)
async def ensure_config_backup_api(
    script: ConfigBackupEnsureIn = Body(...),
) -> ConfigBackupEnsureOut:
    """target 取值由专项池定义（如 zzz-od 的 mas/onedragon、ok-nte 的 mas/native）。"""

    try:
        data = await Config.ensure_config_backup(
            script.scriptId, script.userId, target=script.target
        )
        return ConfigBackupEnsureOut(
            code=200,
            status="success",
            message="",
            **data,
        )
    except ConfigCorruptedError as e:
        # 源配置损坏：message 用原文（含损坏位置）直达用户，前端编辑页会透传
        logger.opt(exception=True).warning(f"配置按需归档失败（源配置损坏）: {e}")
        return ConfigBackupEnsureOut(
            code=400,
            status="error",
            message=str(e),
            created=False,
            time="",
        )
    except Exception as e:
        logger.opt(exception=True).warning(f"配置按需归档失败: {e}")
        return ConfigBackupEnsureOut(
            code=400 if isinstance(e, (ValueError, KeyError, TypeError)) else 500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            created=False,
            time="",
        )


@router.post(
    "/backup/restore",
    tags=["Backup"],
    summary="把指定备份恢复到目标位置（恢复前自动存底当前配置，误恢复可找回）",
    response_model=ConfigBackupRestoreOut,
    status_code=200,
)
async def restore_config_backup_api(
    script: ConfigBackupRestoreIn = Body(...),
) -> ConfigBackupRestoreOut:
    """恢复语义由专项池定义：脚本原生池恢复到脚本本体，MAS 用户池恢复到
    用户配置并按需回填前端表单。备份来自其他配置来源（脚本级/用户级）时
    由服务层把配置来源切回备份时点再恢复；提示由前端据备份列表与当前
    来源比对给出。"""

    try:
        data = await Config.restore_config_backup(
            script.scriptId,
            script.userId,
            script.time,
            target=script.target,
            force=script.force,
        )
        return ConfigBackupRestoreOut(
            code=200,
            status="success",
            message=f"已恢复备份 {script.time}",
            target=data["target"],
        )
    except ConfigCorruptedError as e:
        # 源配置损坏：带损坏位置返回 409，前端弹二次确认后携带 force 重试
        logger.opt(exception=True).warning(f"配置备份恢复被拦截（源配置损坏）: {e}")
        return ConfigBackupRestoreOut(
            code=409,
            status="error",
            message=str(e),
            target=script.target,
        )
    except Exception as e:
        logger.opt(exception=True).warning(f"配置备份恢复失败: {e}")
        return ConfigBackupRestoreOut(
            code=400 if isinstance(e, (ValueError, KeyError, TypeError)) else 500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            target=script.target,
        )


@router.get(
    "/backup/preview",
    tags=["Backup"],
    summary="读取指定备份的配置摘要（纯读不恢复，供「预览配置」快速展示）",
    response_model=ConfigBackupPreviewOut,
    status_code=200,
)
async def get_config_backup_preview_api(
    scriptId: str, userId: str, time: str, target: str
) -> ConfigBackupPreviewOut:
    """data 载荷结构由专项定义（前端按 target 消费）；非法 target 返回 400。"""

    try:
        data = await Config.get_config_backup_preview(
            scriptId, userId, time, target=target
        )
        return ConfigBackupPreviewOut(
            code=200,
            status="success",
            message="",
            **data,
        )
    except Exception as e:
        logger.opt(exception=True).warning(f"配置备份预览失败: {e}")
        return ConfigBackupPreviewOut(
            code=400 if isinstance(e, (ValueError, KeyError, TypeError)) else 500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            time=time,
            target=target,
            data={},
        )


@router.get(
    "/backup/file",
    tags=["Backup"],
    summary="只读读取指定备份内一个文本文件（预览「查看原始文件」用，路径限归档内）",
    response_model=ConfigBackupFileOut,
    status_code=200,
)
async def get_config_backup_file_api(
    scriptId: str, userId: str, time: str, target: str, path: str
) -> ConfigBackupFileOut:
    """路径越界/文件超限/池未实现查看能力均返回 400，message 说明原因。"""

    try:
        data = await Config.get_config_backup_file(
            scriptId, userId, time, target=target, path=path
        )
        return ConfigBackupFileOut(
            code=200,
            status="success",
            message="",
            **data,
        )
    except Exception as e:
        logger.opt(exception=True).warning(f"配置备份文件读取失败: {e}")
        return ConfigBackupFileOut(
            code=400 if isinstance(e, (ValueError, KeyError, TypeError)) else 500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            time=time,
            target=target,
            path=path,
            size=0,
            content="",
        )
