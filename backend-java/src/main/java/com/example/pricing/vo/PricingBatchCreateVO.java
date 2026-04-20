package com.example.pricing.vo;

import lombok.Data;

import java.util.List;

@Data
public class PricingBatchCreateVO {
    private Long batchId;
    private String batchCode;
    private Integer totalCount;
    private List<Long> linkedTaskIds;
    private Integer createFailedCount;
}
