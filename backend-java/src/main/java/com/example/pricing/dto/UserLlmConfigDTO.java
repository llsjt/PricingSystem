/*
 * 用户大模型配置请求对象。
 */

package com.example.pricing.dto;

import lombok.Data;

/**
 * 用户 LLM 配置保存/更新请求体。
 */
@Data
public class UserLlmConfigDTO {
    private String apiKey;
    private String baseUrl;
    private String model;
}
