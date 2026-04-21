/*
 * 商品手工新增或编辑请求对象。
 */

package com.example.pricing.dto;

import lombok.Data;

import java.math.BigDecimal;

/**
 * 手工新增商品请求体，包含基础价格、库存和经营概览字段。
 */
@Data
public class ProductManualDTO {
    private String externalProductId;
    private String productName;
    private String categoryName;
    private BigDecimal costPrice;
    private BigDecimal salePrice;
    private Integer stock;
    private Integer monthlySales = 0;
    private BigDecimal conversionRate = BigDecimal.ZERO;
    private String status = "出售中";
}
