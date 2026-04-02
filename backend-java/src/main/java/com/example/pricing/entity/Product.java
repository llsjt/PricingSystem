package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 商品实体，保存商品基础档案、价格、库存和补充展示字段。
 */
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
