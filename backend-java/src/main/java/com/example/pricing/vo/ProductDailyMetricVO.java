package com.example.pricing.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class ProductDailyMetricVO {
    private Long id;
    private LocalDate statDate;
    private Integer visitorCount;
    private Integer addCartCount;
    private Integer payBuyerCount;
    private Integer salesCount;
    private BigDecimal turnover;
    private BigDecimal refundAmount;
    private BigDecimal conversionRate;
    private LocalDateTime createdAt;
}
