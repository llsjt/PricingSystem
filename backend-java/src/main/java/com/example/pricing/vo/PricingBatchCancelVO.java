package com.example.pricing.vo;

import lombok.Data;

@Data
public class PricingBatchCancelVO {
    private Integer cancelledCount;
    private Integer skippedCount;
}
