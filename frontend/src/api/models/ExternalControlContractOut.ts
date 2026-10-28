/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ExternalControlContractOut = {
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
     * 本机 Python 后端直连地址，不是前端代理或远程桌面宿主地址
     */
    backendUrl?: string;
    /**
     * 当前后端公开输入模型的 JSON Schema
     */
    schemas?: Record<string, any>;
};

