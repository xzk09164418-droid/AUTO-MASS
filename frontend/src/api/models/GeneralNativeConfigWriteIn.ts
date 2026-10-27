/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type GeneralNativeConfigWriteIn = {
    /**
     * 通用脚本 ID
     */
    scriptId: string;
    /**
     * 配置目录内的相对文件名；单文件模式可留空
     */
    file?: string;
    /**
     * 原生配置文本
     */
    content: string;
    /**
     * 读取时的文件指纹，防止覆盖外部修改
     */
    revision: string;
};

