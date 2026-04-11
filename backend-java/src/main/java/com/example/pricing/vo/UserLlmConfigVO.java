package com.example.pricing.vo;

import lombok.Data;

/**
 * 用户 LLM 配置响应体（不返回完整 API Key）。
 */
@Data
public class UserLlmConfigVO {
    private String baseUrl;
    private String model;
    private boolean hasApiKey;
    private String apiKeyPreview;
}
