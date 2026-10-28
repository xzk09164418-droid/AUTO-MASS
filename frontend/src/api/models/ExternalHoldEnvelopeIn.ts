/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ExternalHoldEnvelopeIn = {
    /**
     * UTF-8 JSON 的无填充 Base64URL 编码
     */
    payload: string;
    /**
     * 对 payload 原文计算的 HMAC-SHA256 小写十六进制签名
     */
    signature: string;
};

