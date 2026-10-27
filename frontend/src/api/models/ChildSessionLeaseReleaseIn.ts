/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ChildSessionLeaseReleaseIn = {
    /**
     * 要释放的租约 ID
     */
    leaseId?: (string | null);
    /**
     * 按外部程序名称释放全部关联租约
     */
    caller?: (string | null);
};

