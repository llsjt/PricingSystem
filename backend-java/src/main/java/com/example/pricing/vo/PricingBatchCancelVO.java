package com.example.pricing.vo;

import lombok.Data;

/**
 * 批量定价取消结果视图对象。
 */
@Data
public class PricingBatchCancelVO {
    private Integer cancelledCount;
    private Integer skippedCount;
}
