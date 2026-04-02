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
 * 商品 SKU 实体，记录规格级别的价格、属性和库存信息。
 */
@Data
@TableName("product_sku")
public class ProductSku {
    @TableId(type = IdType.AUTO)
    private Long id;

    @TableField("product_id")
    private Long productId;

    @TableField("external_sku_id")
    private String externalSkuId;

    @TableField("sku_name")
    private String skuName;

    @TableField("sku_attr")
    private String skuAttr;

    @TableField("sale_price")
    private BigDecimal salePrice;

    @TableField("cost_price")
    private BigDecimal costPrice;

    @TableField("stock")
    private Integer stock;

    @TableField(value = "created_at", fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(value = "updated_at", fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
