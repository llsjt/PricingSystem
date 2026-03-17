package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("biz_product")
public class BizProduct {
    @TableId(type = IdType.AUTO)
    private Long id;

    private String title;

    private String category;

    private BigDecimal costPrice;

    private BigDecimal marketPrice;

    private BigDecimal currentPrice;

    private Integer stock;

    private Integer monthlySales;

    private BigDecimal clickRate;

    private BigDecimal conversionRate;

    private String source;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
