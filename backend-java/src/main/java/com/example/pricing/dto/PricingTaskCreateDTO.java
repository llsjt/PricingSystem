/*
 * 单商品定价任务创建请求对象。
 */

package com.example.pricing.dto;

import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 单商品定价任务请求体，供桥接接口创建任务时使用。
 */
@Data
public class PricingTaskCreateDTO {
    private Long productId;

    @Size(max = 1000, message = "constraints length cannot exceed 1000")
    private String constraints;

    @Size(max = 50, message = "strategyGoal length cannot exceed 50")
    private String strategyGoal;
}
