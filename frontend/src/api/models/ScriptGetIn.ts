/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ScriptGetIn = {
    /**
     * 脚本ID, 未携带时表示获取所有脚本数据
     */
    scriptId?: (string | null);
    /**
     * 同时返回各脚本的用户列表
     */
    includeUsers?: boolean;
};

