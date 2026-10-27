/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ChildSessionLeaseAcquireOut = {
    /**
     * 状态码
     */
    code?: number;
    /**
     * 操作状态
     */
    status?: string;
    /**
     * 操作消息
     */
    message?: string;
    /**
     * 租约唯一 ID，供停止使用时回传
     */
    leaseId?: string;
    /**
     * pending（等待当前子任务结束）或 granted（已获准使用）
     */
    leaseStatus?: string;
    /**
     * 当前 Child Session ID
     */
    childSessionId?: (number | null);
    /**
     * 完整租约信息
     */
    lease?: Record<string, any>;
};

