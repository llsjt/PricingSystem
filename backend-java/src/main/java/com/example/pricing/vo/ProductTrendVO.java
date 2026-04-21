/*
 * 商品趋势视图对象。
 */

package com.example.pricing.vo;

import lombok.Data;

import java.util.List;

/**
 * 商品趋势分析视图对象，包含折线图数据和增长指标。
 */
@Data
public class ProductTrendVO {
    private List<String> dates;
    private List<Integer> visitors;
    private List<Integer> sales;
    private List<Double> conversionRates;
    private List<Double> avgOrderValues;

    /**
     * 当前绝对值指标，用于概览卡片展示。
     */
    private Integer currentDailySales;
    private Integer currentMonthlySales;
    private Double currentDailyProfit;
    private Double currentMonthlyProfit;

    /**
     * 增长洞察指标，用于突出近阶段变化趋势。
     */
    private Integer dailySalesGrowth;
    private Double dailySalesGrowthRate;

    private Integer monthlySalesGrowth;
    private Double monthlySalesGrowthRate;

    private Double dailyProfitGrowth;
    private Double dailyProfitGrowthRate;

    private Double monthlyProfitGrowth;
    private Double monthlyProfitGrowthRate;
}
