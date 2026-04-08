package com.example.pricing.vo;

import lombok.Data;

import java.util.List;

@Data
public class PricingTaskSnapshotVO {
    private PricingTaskDetailVO detail;
    private List<DecisionLogVO> logs;
    private List<DecisionComparisonVO> comparison;
}
