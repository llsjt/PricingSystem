package com.example.pricing.vo;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 批量定价详情视图对象。
 */
@Data
public class PricingBatchDetailVO {
    private Long batchId;
    private String batchCode;
    private String batchStatus;
    private String strategyGoal;
    private String constraintText;
    private Integer totalCount;
    private Integer runningCount;
    private Integer completedCount;
    private Integer manualReviewCount;
    private Integer failedCount;
    private Integer cancelledCount;
    private LocalDateTime finalizedAt;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
