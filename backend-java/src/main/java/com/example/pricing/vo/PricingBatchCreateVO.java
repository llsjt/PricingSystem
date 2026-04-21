package com.example.pricing.vo;

import lombok.Data;

import java.util.List;

/**
 * 批量定价创建结果视图对象。
 */
@Data
public class PricingBatchCreateVO {
    private Long batchId;
    private String batchCode;
    private Integer totalCount;
    private List<Long> linkedTaskIds;
    private Integer createFailedCount;
}
