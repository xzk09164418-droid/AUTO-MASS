/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ChildSessionLeaseAcquireIn = {
    /**
     * 申请使用远程桌面的外部程序标识
     */
    caller?: string;
    /**
     * 是否在让渡期间断开 AUTO-MAS 宿主自身的 RDP 预览连接（以便外部程序连接 Child Session）
     */
    disconnectRdpView?: boolean;
    /**
     * 租约最长保护时间（秒），防止外部程序崩溃未回传导致永久挂起
     */
    timeoutSeconds?: number;
    /**
     * 是否阻塞等待至当前正在运行的子任务结束并完成让渡后再返回
     */
    waitForGrant?: boolean;
    /**
     * 当 waitForGrant=True 时的最大等待秒数
     */
    waitTimeout?: number;
};

