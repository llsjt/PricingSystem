package com.example.pricing.vo;

import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class ProductListVO {
    private Long id;
    private String title;
    private String category;
    private BigDecimal costPrice;
    private BigDecimal marketPrice;
    private BigDecimal currentPrice;
    private Integer stock;
    private String source;
    private Integer monthlySales;
    private BigDecimal clickRate;
    private BigDecimal conversionRate;
    private LocalDateTime updatedAt;
}
