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
    
    // Insights
    private Integer dailySalesGrowth; // 日销售量增长量
    private Double dailySalesGrowthRate; // 日销售量增长率
    
    private Integer monthlySalesGrowth; // 月销售量增长量
    private Double monthlySalesGrowthRate; // 月销售量增长率
    
    private Double dailyProfitGrowth; // 日利润增长量
    private Double dailyProfitGrowthRate; // 日利润增长率
    
    private Double monthlyProfitGrowth; // 月利润增长量
    private Double monthlyProfitGrowthRate; // 月利润增长率
}
