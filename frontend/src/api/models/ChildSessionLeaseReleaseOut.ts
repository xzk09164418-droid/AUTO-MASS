/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ChildSessionLeaseReleaseOut = {
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
     * 已释放的租约 ID 列表
     */
    releasedLeaseIds?: Array<string>;
    /**
     * 剩余活跃租约
     */
    remainingLeases?: Array<Record<string, any>>;
};

