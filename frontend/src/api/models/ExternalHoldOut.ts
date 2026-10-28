/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ExternalHoldInfo } from './ExternalHoldInfo';
export type ExternalHoldOut = {
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
    requestId?: string;
    hold?: (ExternalHoldInfo | null);
    remainingHolds?: number;
};

