/*
 * 用户大模型配置视图对象。
 */

package com.example.pricing.vo;

import lombok.Data;

/**
 * 用户 LLM 配置响应体。
 */
@Data
public class UserLlmConfigVO {
    private String baseUrl;
    private String model;
    private boolean hasApiKey;
    private String apiKeyPreview;
    /** 解密后的完整 API Key，供前端回显编辑 */
    private String apiKey;
}
