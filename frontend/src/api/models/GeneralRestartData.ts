/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type GeneralRestartData = {
    /**
     * 启动程序绝对路径
     */
    Path: string;
    /**
     * 启动参数
     */
    Arguments?: string;
    /**
     * 工作目录，留空使用程序目录
     */
    WorkingDirectory?: string;
    /**
     * 启动后等待秒数
     */
    WaitSeconds?: number;
    /**
     * 是否为脚本主体入口
     */
    IsMain?: boolean;
};

