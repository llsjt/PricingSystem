package com.example.pricing.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

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
