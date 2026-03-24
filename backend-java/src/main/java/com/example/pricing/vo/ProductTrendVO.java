package com.example.pricing.vo;

import lombok.Data;

import java.util.List;

@Data
public class ProductTrendVO {
    private List<String> dates;
    private List<Integer> visitors;
    private List<Integer> sales;
    private List<Double> conversionRates;
    private List<Double> avgOrderValues;

    // Absolute values
    private Integer currentDailySales;
    private Integer currentMonthlySales;
    private Double currentDailyProfit;
    private Double currentMonthlyProfit;

    // Insights
    private Integer dailySalesGrowth;
    private Double dailySalesGrowthRate;

    private Integer monthlySalesGrowth;
    private Double monthlySalesGrowthRate;

    private Double dailyProfitGrowth;
    private Double dailyProfitGrowthRate;

    private Double monthlyProfitGrowth;
    private Double monthlyProfitGrowthRate;
}
