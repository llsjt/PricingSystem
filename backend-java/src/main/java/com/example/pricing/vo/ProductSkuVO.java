/*
 * 商品 SKU 视图对象。
 */

package com.example.pricing.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 商品 SKU 视图对象，用于前端展示规格维度的价格和库存。
 */
@Data
public class ProductSkuVO {
    private Long id;
    private String externalSkuId;
    private String skuName;
    private String skuAttr;
    private BigDecimal salePrice;
    private BigDecimal costPrice;
    private Integer stock;
    private LocalDateTime updatedAt;
}
