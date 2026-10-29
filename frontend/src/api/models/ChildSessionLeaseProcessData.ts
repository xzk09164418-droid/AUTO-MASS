/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * 调用方明确授权回收的进程身份；不允许仅凭进程名称认领。
 */
export type ChildSessionLeaseProcessData = {
    pid: number;
    createdAt: number;
    sessionId: number;
};

