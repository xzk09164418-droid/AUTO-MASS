/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ExternalControlSettingsIn = {
    enabled?: boolean;
    email?: string;
    /**
     * 留空保留已有授权码
     */
    authorizationCode?: (string | null);
    callerId?: (string | null);
    /**
     * 新增或轮换调用方密钥，至少 32 字符
     */
    callerSecret?: (string | null);
    removeCaller?: boolean;
};

