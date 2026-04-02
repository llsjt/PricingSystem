package com.example.pricing.dto;

import lombok.Data;

import java.util.List;

/**
 * 决策任务创建请求体，承载待分析商品、策略目标和约束条件。
 */
@Data
public class DecisionTaskDTO {
    private List<Long> productIds;
    private String strategyGoal;
    private String constraints;
}
