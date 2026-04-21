package com.example.pricing.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 批量定价子项视图对象。
 */
@Data
public class PricingBatchItemVO {
    private Long id;
    private Long batchId;
    private Integer itemOrder;
    private Long productId;
    private Long taskId;
    private Long resultId;
    private String productTitle;
    private BigDecimal currentPrice;
    private BigDecimal finalPrice;
    private Integer expectedSales;
    private BigDecimal expectedProfit;
    private BigDecimal profitGrowth;
    private String creationStatus;
    private String taskStatus;
    private String displayStatus;
    private String executeStrategy;
    private Boolean reviewRequired;
    private String appliedStatus;
    private String errorMessage;
    private LocalDateTime createdAt;
    private LocalDateTime batchItemUpdatedAt;
    private LocalDateTime taskUpdatedAt;
    private LocalDateTime updatedAt;
}
