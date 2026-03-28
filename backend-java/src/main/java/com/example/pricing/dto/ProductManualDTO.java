package com.example.pricing.dto;

import lombok.Data;
import java.math.BigDecimal;

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
    private String status = "ON_SALE";
}
