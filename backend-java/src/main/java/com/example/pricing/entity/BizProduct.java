package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("product")
public class BizProduct {
    @TableId(type = IdType.AUTO)
    private Long id;

    private Long shopId;

    private Long itemId;

    @TableField("product_name")
    private String title;

    @TableField("category_name")
    private String category;

    private BigDecimal costPrice;

    @TableField(exist = false)
    private BigDecimal marketPrice;

    @TableField("sale_price")
    private BigDecimal currentPrice;

    private Integer stock;

    private String status;

    @TableField(exist = false)
    private Integer monthlySales;

    @TableField(exist = false)
    private BigDecimal clickRate;

    @TableField(exist = false)
    private BigDecimal conversionRate;

    @TableField(exist = false)
    private String source;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
