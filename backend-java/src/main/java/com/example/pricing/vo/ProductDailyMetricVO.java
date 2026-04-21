/*
 * 商品日指标视图对象。
 */

package com.example.pricing.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 商品日经营指标视图对象，用于前端展示经营明细表格。
 */
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
