package com.example.pricing.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 决策任务列表视图对象，用于任务列表页展示摘要信息。
 */
@Data
public class DecisionTaskItemVO {
    private Long id;
    private String taskCode;
    private Long productId;
    private String productTitle;
    private BigDecimal currentPrice;
    private BigDecimal suggestedMinPrice;
    private BigDecimal suggestedMaxPrice;
    private BigDecimal finalPrice;
    private String taskStatus;
    private String executeStrategy;
    private LocalDateTime createdAt;
}
