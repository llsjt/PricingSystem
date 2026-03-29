package com.example.pricing.dto;

import lombok.Data;

/**
 * 前端发起定价任务请求体。
 */
@Data
public class PricingTaskCreateDTO {
    private Long productId;
    private String constraints;
    private String strategyGoal;
}
