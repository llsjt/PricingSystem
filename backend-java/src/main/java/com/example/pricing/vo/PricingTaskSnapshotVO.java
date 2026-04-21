package com.example.pricing.vo;

import lombok.Data;

import java.util.List;

/**
 * 定价任务快照视图对象，聚合详情、日志和结果对比。
 */
@Data
public class PricingTaskSnapshotVO {
    private PricingTaskDetailVO detail;
    private List<DecisionLogVO> logs;
    private List<DecisionComparisonVO> comparison;
}
