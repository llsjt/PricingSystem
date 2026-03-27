package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("product")
public class Product {
    @TableId(type = IdType.AUTO)
    private Long id;

    @TableField("shop_id")
    private Long shopId;

    @TableField("external_product_id")
    private String externalProductId;

    @TableField("product_name")
    private String title;

    @TableField("category_name")
    private String category;

    @TableField("cost_price")
    private BigDecimal costPrice;

    @TableField(exist = false)
    private BigDecimal marketPrice;

    @TableField("sale_price")
    private BigDecimal currentPrice;

    @TableField("stock")
    private Integer stock;

    @TableField("status")
    private String status;

    @TableField("profile_status")
    private String profileStatus;

    @TableField(exist = false)
    private Integer monthlySales;

    @TableField(exist = false)
    private BigDecimal clickRate;

    @TableField(exist = false)
    private BigDecimal conversionRate;

    @TableField(exist = false)
    private String source;

    @TableField(value = "created_at", fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(value = "updated_at", fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
