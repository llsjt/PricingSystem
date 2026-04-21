/*
 * 定价任务详情视图对象。
 */

package com.example.pricing.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 定价任务详情视图对象，用于展示单个任务的完整输出信息。
 */
@Data
public class PricingTaskDetailVO {
    private Long taskId;
    private Long productId;
    private String productTitle;
    private String taskStatus;
    private BigDecimal currentPrice;
    private BigDecimal suggestedMinPrice;
    private BigDecimal suggestedMaxPrice;
    private BigDecimal finalPrice;
    private Integer expectedSales;
    private BigDecimal expectedProfit;
    private String strategy;
    private String finalSummary;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
