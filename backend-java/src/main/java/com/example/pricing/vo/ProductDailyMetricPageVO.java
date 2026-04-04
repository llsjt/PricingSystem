package com.example.pricing.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

@Data
public class ProductDailyMetricPageVO {
    private long page;
    private long size;
    private long total;
    private List<ProductDailyMetricVO> records = new ArrayList<>();
    private Summary summary = new Summary();

    @Data
    public static class Summary {
        private long days;
        private long totalVisitors;
        private BigDecimal totalTurnover = BigDecimal.ZERO;
        private BigDecimal avgConversionRate = BigDecimal.ZERO;
    }
}
