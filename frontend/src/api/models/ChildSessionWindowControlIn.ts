/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ChildSessionWindowControlIn = {
    /**
     * 显示或隐藏远程桌面窗口
     */
    visible?: (boolean | null);
    /**
     * 观看模式（屏蔽本机键鼠输入进入分身）
     */
    watchMode?: (boolean | null);
    /**
     * 画面自适应窗口缩放
     */
    smartSizing?: (boolean | null);
    /**
     * 窗口置顶
     */
    topmost?: (boolean | null);
    /**
     * 向远程桌面发送组合键，如 Win+D 或 Win+Tab
     */
    shortcut?: (string | null);
};

