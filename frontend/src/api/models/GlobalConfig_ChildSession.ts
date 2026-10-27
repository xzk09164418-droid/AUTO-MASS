/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type GlobalConfig_ChildSession = {
    /**
     * 是否启用基于 BetterGI 的本地远程桌面 (Child Session) 执行任务
     */
    Enabled?: (boolean | null);
    /**
     * C# 远程桌面宿主 IPC 端口
     */
    HostPort?: (number | null);
    /**
     * 远程桌面分辨率，形如 1920x1080
     */
    Resolution?: (string | null);
    /**
     * 启动时是否隐藏远程桌面窗口
     */
    StartHidden?: (boolean | null);
    /**
     * 是否开启观看模式（屏蔽本机键鼠输入进入分身）
     */
    WatchMode?: (boolean | null);
};

