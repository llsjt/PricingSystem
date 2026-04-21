/*
 * 单商品定价任务创建请求对象。
 */

package com.example.pricing.dto;

import lombok.Data;

/**
 * 单商品定价任务请求体，供桥接接口创建任务时使用。
 */
@Data
public class PricingTaskCreateDTO {
    private Long productId;
    private String constraints;
    private String strategyGoal;
}
