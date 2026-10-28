/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ExternalControlSettingsData } from './ExternalControlSettingsData';
import type { ExternalHoldInfo } from './ExternalHoldInfo';
import type { ExternalHoldOut } from './ExternalHoldOut';
export type ExternalControlSnapshotOut = {
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
    settings?: ExternalControlSettingsData;
    holds?: Array<ExternalHoldInfo>;
    results?: Array<ExternalHoldOut>;
    mailError?: string;
};

