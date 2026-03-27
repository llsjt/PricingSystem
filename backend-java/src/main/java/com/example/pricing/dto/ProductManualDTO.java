package com.example.pricing.dto;

import lombok.Data;
import java.math.BigDecimal;

@Data
public class ProductManualDTO {
    private String itemId;
    private String title;
    private String category;
    private BigDecimal costPrice;
    private BigDecimal currentPrice;
    private Integer stock;
    private Integer monthlySales = 0;
    private BigDecimal conversionRate = BigDecimal.ZERO;
    private String status = "ON_SALE";
}
