/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BlueArchiveActivityIn } from '../models/BlueArchiveActivityIn';
import type { ComboBoxOut } from '../models/ComboBoxOut';
import type { Emulator2AvdInstanceIn } from '../models/Emulator2AvdInstanceIn';
import type { Emulator2AvdInstanceOptionsOut } from '../models/Emulator2AvdInstanceOptionsOut';
import type { Emulator2AvdStatusIn } from '../models/Emulator2AvdStatusIn';
import type { Emulator2AvdStatusOut } from '../models/Emulator2AvdStatusOut';
import type { Emulator2DevicesIn } from '../models/Emulator2DevicesIn';
import type { Emulator2DevicesOut } from '../models/Emulator2DevicesOut';
import type { Emulator2InstanceDeleteIn } from '../models/Emulator2InstanceDeleteIn';
import type { Emulator2InstanceDeletePreviewOut } from '../models/Emulator2InstanceDeletePreviewOut';
import type { Emulator2PathRemoveIn } from '../models/Emulator2PathRemoveIn';
import type { Emulator2PathRemovePreviewOut } from '../models/Emulator2PathRemovePreviewOut';
import type { Emulator2SearchIn } from '../models/Emulator2SearchIn';
import type { Emulator2SearchOut } from '../models/Emulator2SearchOut';
import type { EmulatorDeleteIn } from '../models/EmulatorDeleteIn';
import type { EmulatorGetIn } from '../models/EmulatorGetIn';
import type { EmulatorGetOut } from '../models/EmulatorGetOut';
import type { EmulatorSearchOut } from '../models/EmulatorSearchOut';
import type { EmulatorStatusOut } from '../models/EmulatorStatusOut';
import type { GameCalendarActivitiesOut } from '../models/GameCalendarActivitiesOut';
import type { HistoryDataGetIn } from '../models/HistoryDataGetIn';
import type { HistoryDataGetOut } from '../models/HistoryDataGetOut';
import type { HistorySearchIn } from '../models/HistorySearchIn';
import type { HistorySearchOut } from '../models/HistorySearchOut';
import type { InfoOut } from '../models/InfoOut';
import type { NoticeOut } from '../models/NoticeOut';
import type { NotifyChannelsOut } from '../models/NotifyChannelsOut';
import type { ObsReplayCheckOut } from '../models/ObsReplayCheckOut';
import type { PowerCountdownSnapshot } from '../models/PowerCountdownSnapshot';
import type { PowerOut } from '../models/PowerOut';
import type { QueueGetIn } from '../models/QueueGetIn';
import type { QueueGetOut } from '../models/QueueGetOut';
import type { QueueItemGetIn } from '../models/QueueItemGetIn';
import type { QueueItemGetOut } from '../models/QueueItemGetOut';
import type { ReplayListOut } from '../models/ReplayListOut';
import type { ScriptGetIn } from '../models/ScriptGetIn';
import type { ScriptGetOut } from '../models/ScriptGetOut';
import type { ScriptShareInspectIn } from '../models/ScriptShareInspectIn';
import type { SettingGetOut } from '../models/SettingGetOut';
import type { ShareAppearanceCategoryIn } from '../models/ShareAppearanceCategoryIn';
import type { ShareAppearanceCoverIn } from '../models/ShareAppearanceCoverIn';
import type { ShareAppearanceCoverOut } from '../models/ShareAppearanceCoverOut';
import type { ShareAppearanceMineOut } from '../models/ShareAppearanceMineOut';
import type { ShareAppearanceUploadsOut } from '../models/ShareAppearanceUploadsOut';
import type { ShareAuthStatusOut } from '../models/ShareAuthStatusOut';
import type { ShareInspectOut } from '../models/ShareInspectOut';
import type { ShareTemplateListIn } from '../models/ShareTemplateListIn';
import type { ShareTemplateListOut } from '../models/ShareTemplateListOut';
import type { TaskRuntimeSnapshot } from '../models/TaskRuntimeSnapshot';
import type { TaskStatusOut } from '../models/TaskStatusOut';
import type { TimeSetGetIn } from '../models/TimeSetGetIn';
import type { TimeSetGetOut } from '../models/TimeSetGetOut';
import type { ToolsGetOut } from '../models/ToolsGetOut';
import type { UpdateCheckIn } from '../models/UpdateCheckIn';
import type { UpdateCheckOut } from '../models/UpdateCheckOut';
import type { UpdateDownloadSnapshot } from '../models/UpdateDownloadSnapshot';
import type { UserConfigDirIn } from '../models/UserConfigDirIn';
import type { UserConfigDirOut } from '../models/UserConfigDirOut';
import type { UserGetIn } from '../models/UserGetIn';
import type { UserGetOut } from '../models/UserGetOut';
import type { VersionOut } from '../models/VersionOut';
import type { VirtualDisplayCheckOut } from '../models/VirtualDisplayCheckOut';
import type { WebhookGetIn } from '../models/WebhookGetIn';
import type { WebhookGetOut } from '../models/WebhookGetOut';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class GetService {
    /**
     * 获取游戏已完成活动
     * @param game
     * @param server
     * @returns GameCalendarActivitiesOut Successful Response
     * @throws ApiError
     */
    public static getActivityCompletionsApiInfoActivityCompletionsGet(
        game: 'endfield' | 'starrail' | 'genshin' | 'zenless' | 'wutheringwaves' | 'nte' | 'reverse1999' | 'bluearchive' | 'arknights' | 'stellasora' | 'infinitynikki',
        server: 'cn' | 'jp' | 'global' = 'cn',
    ): CancelablePromise<GameCalendarActivitiesOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/info/activity/completions',
            query: {
                'game': game,
                'server': server,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取后端git版本信息
     * @returns VersionOut Successful Response
     * @throws ApiError
     */
    public static getGitVersionApiInfoVersionPost(): CancelablePromise<VersionOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/info/version',
        });
    }
    /**
     * 获取脚本下拉框信息
     * @returns ComboBoxOut Successful Response
     * @throws ApiError
     */
    public static getScriptComboxApiInfoComboxScriptPost(): CancelablePromise<ComboBoxOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/info/combox/script',
        });
    }
    /**
     * 获取可选任务下拉框信息
     * @returns ComboBoxOut Successful Response
     * @throws ApiError
     */
    public static getTaskComboxApiInfoComboxTaskPost(): CancelablePromise<ComboBoxOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/info/combox/task',
        });
    }
    /**
     * 获取可选模拟器下拉框信息
     * @returns ComboBoxOut Successful Response
     * @throws ApiError
     */
    public static getEmulatorComboxApiInfoComboxEmulatorPost(): CancelablePromise<ComboBoxOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/info/combox/emulator',
        });
    }
    /**
     * 获取可选模拟器多开实例下拉框信息
     * @param requestBody
     * @returns ComboBoxOut Successful Response
     * @throws ApiError
     */
    public static getEmulatorDevicesComboxApiInfoComboxEmulatorDevicesPost(
        requestBody: EmulatorDeleteIn,
    ): CancelablePromise<ComboBoxOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/info/combox/emulator/devices',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取通知信息
     * @returns NoticeOut Successful Response
     * @throws ApiError
     */
    public static getNoticeInfoApiInfoNoticeGetPost(): CancelablePromise<NoticeOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/info/notice/get',
        });
    }
    /**
     * 信息总览
     * @param refresh
     * @returns InfoOut Successful Response
     * @throws ApiError
     */
    public static getOverviewApiInfoGetOverviewPost(
        refresh: boolean = false,
    ): CancelablePromise<InfoOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/info/get/overview',
            query: {
                'refresh': refresh,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取碧蓝档案活动数据（GameKee 中转）
     * 按服务器取回碧蓝档案的活动。
     *
     * 这里只做转发：把 GameKee 的响应原样交给前端，分类筛选与格式转换都由前端完成。
     * 之所以要绕一道后端，一是那个接口认自定义头、二是响应没给跨域头，浏览器直连取不到。
     *
     * GameKee 取不到时改用 SRA 托管的那份：那一份已经筛掉非活动条目，这里换成 GameKee
     * 的字段形状再交给前端，省得让前端认识第二套数据源。
     * @param requestBody
     * @returns InfoOut Successful Response
     * @throws ApiError
     */
    public static getBluearchiveActivityApiInfoBluearchiveActivityPost(
        requestBody: BlueArchiveActivityIn,
    ): CancelablePromise<InfoOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/info/bluearchive/activity',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取碧蓝档案活动图片（GameKee 中转）
     * 中转 GameKee 的图片。
     *
     * 那个 CDN 校验 Referer：带上它自己的站点才给图，页面直连（Referer 是本软件）会被拒。
     * 所以图片也由后端取回，前端只管引用这个地址。
     * @param url 图片地址
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getBluearchiveImageApiInfoBluearchiveImageGet(
        url: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/info/bluearchive/image',
            query: {
                'url': url,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取终末地版本图与版本名
     * 终末地的版本图地址与版本名（图是固定地址，前端再走图片中转取回）。
     *
     * 给出地址的同时顺手把那张图热进缓存：它有 5MB 级，前端拿到地址才现下载的话，
     * 横幅要空着等好几秒。
     * @returns InfoOut Successful Response
     * @throws ApiError
     */
    public static getEndfieldVersionArtApiInfoEndfieldVersionArtGet(): CancelablePromise<InfoOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/info/endfield/version-art',
        });
    }
    /**
     * 获取终末地活动图片（缩放后转发）
     * 把终末地的活动大图缩到横幅宽度再交给前端。
     * @param url 图片地址
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getEndfieldImageApiInfoEndfieldImageGet(
        url: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/info/endfield/image',
            query: {
                'url': url,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取明日方舟活动数据（PRTS 中转）
     * 取回明日方舟的活动一览。
     *
     * PRTS 的页面里已经带了活动名、分类、起止时间与配图，这里解析成前端好用的形状。
     * 最近两周一场活动都没有是正常情况（长草期），按空列表返回并照常缓存，
     * 不然前端会把「没有活动」当成接口出错反复重试。
     *
     * PRTS 在部分网络下会连不上、也挡浏览器直连，真取不到时改用 SRA 托管的那份活动列表
     * 顶上：数据没有活动分类，卡片上会少一列标签，但至少不是空的。
     * @returns InfoOut Successful Response
     * @throws ApiError
     */
    public static getArknightsActivityApiInfoArknightsActivityGet(): CancelablePromise<InfoOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/info/arknights/activity',
        });
    }
    /**
     * 获取星塔旅人活动数据（官网公告）
     * 取回星塔旅人的活动一览。
     *
     * 数据取自国服官网的活动公告：官网 CMS 不放开跨域、也认 Referer，所以由后端
     * 取回并按公告正文里的开放时间整理成与其它游戏一致的形状。
     *
     * 官网取不到、或者这一次一篇活动公告都没识别出来时，改用 SRA 托管的那份顶上：
     * 对方的抓取在它自己的服务器上完成，用户本机到不了官网也能看到活动。那份数据没有
     * 分类，按本模块给星塔旅人定的判据补一个，否则前端的横幅与常驻分组会全落空。
     *
     * Returns:
     * InfoOut: ``{"activities": [...]}``；两处都取不到时返回 ``code=500`` 的错误信封。
     * @returns InfoOut Successful Response
     * @throws ApiError
     */
    public static getStellaActivityApiInfoStellaActivityPost(): CancelablePromise<InfoOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/info/stella/activity',
        });
    }
    /**
     * 查询脚本配置信息
     * @param requestBody
     * @returns ScriptGetOut Successful Response
     * @throws ApiError
     */
    public static getScriptApiScriptsGetPost(
        requestBody: ScriptGetIn,
    ): CancelablePromise<ScriptGetOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/scripts/get',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 分享前检查脚本配置中的隐私风险
     * @param requestBody
     * @returns ShareInspectOut Successful Response
     * @throws ApiError
     */
    public static inspectScriptShareApiScriptsShareInspectPost(
        requestBody: ScriptShareInspectIn,
    ): CancelablePromise<ShareInspectOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/scripts/share/inspect',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询用户
     * @param requestBody
     * @returns UserGetOut Successful Response
     * @throws ApiError
     */
    public static getUserApiScriptsUserGetPost(
        requestBody: UserGetIn,
    ): CancelablePromise<UserGetOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/scripts/user/get',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取用户配置目录
     * @param requestBody
     * @returns UserConfigDirOut Successful Response
     * @throws ApiError
     */
    public static getUserConfigDirApiScriptsUserConfigDirPost(
        requestBody: UserConfigDirIn,
    ): CancelablePromise<UserConfigDirOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/scripts/user/config-dir',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询 webhook 配置
     * @param requestBody
     * @returns WebhookGetOut Successful Response
     * @throws ApiError
     */
    public static getWebhookApiScriptsWebhookGetPost(
        requestBody: WebhookGetIn,
    ): CancelablePromise<WebhookGetOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/scripts/webhook/get',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询模拟器配置
     * @param requestBody
     * @returns EmulatorGetOut Successful Response
     * @throws ApiError
     */
    public static getEmulatorApiEmulatorGetPost(
        requestBody: EmulatorGetIn,
    ): CancelablePromise<EmulatorGetOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/emulator/get',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询模拟器状态
     * @param requestBody
     * @returns EmulatorStatusOut Successful Response
     * @throws ApiError
     */
    public static getStatusApiEmulatorStatusPost(
        requestBody: EmulatorGetIn,
    ): CancelablePromise<EmulatorStatusOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/emulator/status',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 搜索已安装的模拟器
     * 枚举卸载表并解析主管理器路径（不依赖 ADB 设备枚举）。
     * @returns EmulatorSearchOut Successful Response
     * @throws ApiError
     */
    public static searchEmulatorsApiEmulatorEmulatorSearchPost(): CancelablePromise<EmulatorSearchOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/emulator/emulator/search',
        });
    }
    /**
     * 搜索可加入 Emulator 2.0 的模拟器
     * 列出本机模拟器并逐条判定。不可添加的**也会列出**并给出原因枚举。
     * @param requestBody
     * @returns Emulator2SearchOut Successful Response
     * @throws ApiError
     */
    public static searchEmulatorsApiEmulator2SearchPost(
        requestBody?: Emulator2SearchIn,
    ): CancelablePromise<Emulator2SearchOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/emulator2/search',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 预览移除模拟器路径的影响
     * 只读。列出会失效的设备号与受影响的脚本，供确认页使用。
     * @param requestBody
     * @returns Emulator2PathRemovePreviewOut Successful Response
     * @throws ApiError
     */
    public static previewRemovePathApiEmulator2PathsRemovePreviewPost(
        requestBody: Emulator2PathRemoveIn,
    ): CancelablePromise<Emulator2PathRemovePreviewOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/emulator2/paths/remove/preview',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询合并后的设备列表
     * 合并多条安装的实例。键是设备号，另附模拟器自己的实例索引。
     *
     * 枚举失败的安装标 ``unavailable``——一次枚举失败不等于实例被删除，
     * 既不写墓碑也不影响下次恢复。``withSettings=false`` 只取状态，给轮询用。
     * @param requestBody
     * @returns Emulator2DevicesOut Successful Response
     * @throws ApiError
     */
    public static listDevicesApiEmulator2DevicesPost(
        requestBody: Emulator2DevicesIn,
    ): CancelablePromise<Emulator2DevicesOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/emulator2/devices',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 预览删除实例的影响
     * 只读。列出绑定了该设备号的脚本，供确认页使用。
     * @param requestBody
     * @returns Emulator2InstanceDeletePreviewOut Successful Response
     * @throws ApiError
     */
    public static previewDeleteInstanceApiEmulator2InstancesDeletePreviewPost(
        requestBody: Emulator2InstanceDeleteIn,
    ): CancelablePromise<Emulator2InstanceDeletePreviewOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/emulator2/instances/delete/preview',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询魔改 AVD 根目录的组件状态
     * 组件清单与是否齐全（缺哪几项）、硬件加速（WHPX）是否可用、开机前电脑检查。
     * 组件随模拟器内测包提供，MAS 不下载。只读，不联网。``refresh`` 为 true 时检查不走缓存。
     * @param requestBody
     * @returns Emulator2AvdStatusOut Successful Response
     * @throws ApiError
     */
    public static avdStatusApiEmulator2AvdStatusPost(
        requestBody: Emulator2AvdStatusIn,
    ): CancelablePromise<Emulator2AvdStatusOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/emulator2/avd/status',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询魔改 AVD 实例选项
     * 显示档位、内存、核数、数据盘、首次初始化与渲染器检测结果、端口。
     * @param requestBody
     * @returns Emulator2AvdInstanceOptionsOut Successful Response
     * @throws ApiError
     */
    public static avdInstanceOptionsApiEmulator2AvdInstanceOptionsPost(
        requestBody: Emulator2AvdInstanceIn,
    ): CancelablePromise<Emulator2AvdInstanceOptionsOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/emulator2/avd/instance/options',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询调度队列配置信息
     * @param requestBody
     * @returns QueueGetOut Successful Response
     * @throws ApiError
     */
    public static getQueuesApiQueueGetPost(
        requestBody: QueueGetIn,
    ): CancelablePromise<QueueGetOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/queue/get',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询定时项
     * @param requestBody
     * @returns TimeSetGetOut Successful Response
     * @throws ApiError
     */
    public static getTimeSetApiQueueTimeGetPost(
        requestBody: TimeSetGetIn,
    ): CancelablePromise<TimeSetGetOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/queue/time/get',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询队列项
     * @param requestBody
     * @returns QueueItemGetOut Successful Response
     * @throws ApiError
     */
    public static getItemApiQueueItemGetPost(
        requestBody: QueueItemGetIn,
    ): CancelablePromise<QueueItemGetOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/queue/item/get',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取运行中任务初始快照
     * 返回当前运行任务；WS 只承载后续状态、日志与完成事件。
     * @returns TaskRuntimeSnapshot Successful Response
     * @throws ApiError
     */
    public static getTaskRuntimeSnapshotApiDispatchRuntimeSnapshotGet(): CancelablePromise<TaskRuntimeSnapshot> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/dispatch/runtime-snapshot',
        });
    }
    /**
     * 按 taskId 查询单个任务状态
     * 返回运行中或最近完成任务的终态；不包含日志。
     * @param taskId
     * @returns TaskStatusOut Successful Response
     * @throws ApiError
     */
    public static getTaskStatusApiDispatchTaskTaskIdGet(
        taskId: string,
    ): CancelablePromise<TaskStatusOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/dispatch/task/{task_id}',
            path: {
                'task_id': taskId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取电源倒计时初始快照
     * 返回当前倒计时；WS 只承载后续逐秒更新与取消事件。
     * @returns PowerCountdownSnapshot Successful Response
     * @throws ApiError
     */
    public static getPowerCountdownSnapshotApiDispatchPowerCountdownSnapshotGet(): CancelablePromise<PowerCountdownSnapshot> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/dispatch/power/countdown-snapshot',
        });
    }
    /**
     * 获取电源标志
     * @returns PowerOut Successful Response
     * @throws ApiError
     */
    public static getPowerApiDispatchGetPowerPost(): CancelablePromise<PowerOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/dispatch/get/power',
        });
    }
    /**
     * 查询保留的失败回放
     * @returns ReplayListOut Successful Response
     * @throws ApiError
     */
    public static getObsReplaysApiHistoryReplaysGet(): CancelablePromise<ReplayListOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/history/replays',
        });
    }
    /**
     * 搜索历史记录总览信息
     * @param requestBody
     * @returns HistorySearchOut Successful Response
     * @throws ApiError
     */
    public static searchHistoryApiHistorySearchPost(
        requestBody: HistorySearchIn,
    ): CancelablePromise<HistorySearchOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/history/search',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 从指定文件内获取历史记录数据
     * @param requestBody
     * @returns HistoryDataGetOut Successful Response
     * @throws ApiError
     */
    public static getHistoryDataApiHistoryDataPost(
        requestBody: HistoryDataGetIn,
    ): CancelablePromise<HistoryDataGetOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/history/data',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询工具配置
     * 获取工具设置
     * @returns ToolsGetOut Successful Response
     * @throws ApiError
     */
    public static getToolsApiToolsGetPost(): CancelablePromise<ToolsGetOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/tools/get',
        });
    }
    /**
     * 检查 OBS 回放缓冲
     * @returns ObsReplayCheckOut Successful Response
     * @throws ApiError
     */
    public static checkObsReplayApiSettingObsCheckPost(): CancelablePromise<ObsReplayCheckOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/setting/obs/check',
        });
    }
    /**
     * 导出数据备份
     * 导出数据、配置与历史记录。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static backupDataApiSettingBackupGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/setting/backup',
        });
    }
    /**
     * 查询配置
     * 查询配置
     * @returns SettingGetOut Successful Response
     * @throws ApiError
     */
    public static getScriptsApiSettingGetPost(): CancelablePromise<SettingGetOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/setting/get',
        });
    }
    /**
     * 查询通知渠道描述
     * 返回通知渠道描述表，仅展示元数据，不含任何配置值。
     * @returns NotifyChannelsOut Successful Response
     * @throws ApiError
     */
    public static getNotifyChannelsApiSettingNotifyChannelsGet(): CancelablePromise<NotifyChannelsOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/setting/notify/channels',
        });
    }
    /**
     * 查询 webhook 配置
     * @param requestBody
     * @returns WebhookGetOut Successful Response
     * @throws ApiError
     */
    public static getWebhookApiSettingWebhookGetPost(
        requestBody: WebhookGetIn,
    ): CancelablePromise<WebhookGetOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/setting/webhook/get',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 检测虚拟显示驱动
     * 三段式检测虚拟显示驱动。
     *
     * 前两段验「能不能调用」，第三段真插一块屏再拆掉，验「有没有效果」——只做前两段
     * 会出现「设置页显示检测通过、无人值守时照样失败」的假信号。第三段会真的改变桌面
     * 拓扑，所以只挂在用户手动触发的按钮上，不在任务流程里自动跑。
     * @returns VirtualDisplayCheckOut Successful Response
     * @throws ApiError
     */
    public static checkVirtualDisplayApiSettingVirtualDisplayCheckPost(): CancelablePromise<VirtualDisplayCheckOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/setting/virtual-display/check',
        });
    }
    /**
     * 查询虚拟显示驱动状态
     * 只查驱动装没装、能不能调，不改变桌面拓扑。
     *
     * 设置页打开时自动调用，用来决定开关能不能打开。不做缓存也不持久化：一次 0.2ms，
     * 而存下来的状态只会变陈旧。
     * @returns VirtualDisplayCheckOut Successful Response
     * @throws ApiError
     */
    public static virtualDisplayStatusApiSettingVirtualDisplayStatusPost(): CancelablePromise<VirtualDisplayCheckOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/setting/virtual-display/status',
        });
    }
    /**
     * 获取配置中心已发布的通用脚本配置
     * @param requestBody
     * @returns ShareTemplateListOut Successful Response
     * @throws ApiError
     */
    public static listShareTemplatesApiShareTemplatesPost(
        requestBody: ShareTemplateListIn,
    ): CancelablePromise<ShareTemplateListOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/share/templates',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取配置中心授权状态
     * @returns ShareAuthStatusOut Successful Response
     * @throws ApiError
     */
    public static getShareAuthStatusApiShareAuthStatusPost(): CancelablePromise<ShareAuthStatusOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/share/auth/status',
        });
    }
    /**
     * 轮询配置中心授权结果
     * @returns ShareAuthStatusOut Successful Response
     * @throws ApiError
     */
    public static pollShareAuthApiShareAuthPollPost(): CancelablePromise<ShareAuthStatusOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/share/auth/poll',
        });
    }
    /**
     * 获取当前账号的外观上传记录
     * @param requestBody
     * @returns ShareAppearanceUploadsOut Successful Response
     * @throws ApiError
     */
    public static listShareAppearanceUploadsApiShareAppearanceUploadsPost(
        requestBody?: ShareAppearanceCategoryIn,
    ): CancelablePromise<ShareAppearanceUploadsOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/share/appearance/uploads',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取当前账号在分享站上的全部外观
     * @param requestBody
     * @returns ShareAppearanceMineOut Successful Response
     * @throws ApiError
     */
    public static listMyShareAppearancesApiShareAppearanceMinePost(
        requestBody?: ShareAppearanceCategoryIn,
    ): CancelablePromise<ShareAppearanceMineOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/share/appearance/mine',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取自己外观某个版本的封面
     * @param requestBody
     * @returns ShareAppearanceCoverOut Successful Response
     * @throws ApiError
     */
    public static getMyShareAppearanceCoverApiShareAppearanceCoverPost(
        requestBody: ShareAppearanceCoverIn,
    ): CancelablePromise<ShareAppearanceCoverOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/share/appearance/cover',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取更新下载初始快照
     * 返回当前下载权威状态；WS 只承载后续进度与终态事件。
     * @returns UpdateDownloadSnapshot Successful Response
     * @throws ApiError
     */
    public static getUpdateDownloadStatusApiUpdateDownloadStatusGet(): CancelablePromise<UpdateDownloadSnapshot> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/update/download/status',
        });
    }
    /**
     * 检查更新
     * @param requestBody
     * @returns UpdateCheckOut Successful Response
     * @throws ApiError
     */
    public static checkUpdateApiUpdateCheckPost(
        requestBody: UpdateCheckIn,
    ): CancelablePromise<UpdateCheckOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/update/check',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
