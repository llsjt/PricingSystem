package com.example.pricing.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 商品列表视图对象，用于列表页展示商品概览信息。
 */
@Data
public class ProductListVO {
    private Long id;
    private String platform;
    private String externalProductId;
    private String productName;
    private String categoryName;
    private BigDecimal costPrice;
    private BigDecimal salePrice;
    private Integer stock;
    private String status;
    private Integer monthlySales;
    private BigDecimal conversionRate;
    private LocalDateTime updatedAt;
}
