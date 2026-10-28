/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GeneralOwnershipAnswerIn } from '../models/GeneralOwnershipAnswerIn';
import type { GeneralOwnershipPromptsOut } from '../models/GeneralOwnershipPromptsOut';
import type { OutBase } from '../models/OutBase';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class GeneralOwnershipService {
    /**
     * Get Ownership Prompts
     * @returns GeneralOwnershipPromptsOut Successful Response
     * @throws ApiError
     */
    public static getOwnershipPromptsApiScriptsOwnershipPromptsGet(): CancelablePromise<GeneralOwnershipPromptsOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/scripts/ownership/prompts',
        });
    }
    /**
     * Answer Ownership Prompt
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static answerOwnershipPromptApiScriptsOwnershipAnswerPost(
        requestBody: GeneralOwnershipAnswerIn,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/scripts/ownership/answer',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
