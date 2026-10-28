/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ExternalHoldInfo = {
    holdId: string;
    callerId: string;
    scriptId: string;
    state: ExternalHoldInfo.state;
    /**
     * UTC Unix 秒
     */
    expiresAt: number;
    message?: string;
};
export namespace ExternalHoldInfo {
    export enum state {
        STOPPING = 'stopping',
        ACTIVE = 'active',
        RELEASED = 'released',
        EXPIRED = 'expired',
        FAILED = 'failed',
    }
}

