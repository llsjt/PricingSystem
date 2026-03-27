package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@TableName("product_daily_metric")
public class ProductDailyMetric {
    @TableId(type = IdType.AUTO)
    private Long id;

    @TableField("shop_id")
    private Long shopId;

    @TableField("product_id")
    private Long productId;

    @TableField("stat_date")
    private LocalDate statDate;

    @TableField("visitor_count")
    private Integer visitorCount;

    @TableField("add_cart_count")
    private Integer addCartCount;

    @TableField("pay_buyer_count")
    private Integer payBuyerCount;

    @TableField("pay_item_qty")
    private Integer salesCount;

    @TableField("pay_amount")
    private BigDecimal turnover;

    @TableField("refund_amount")
    private BigDecimal refundAmount;

    @TableField("convert_rate")
    private BigDecimal conversionRate;

    @TableField("upload_batch_id")
    private Long uploadBatchId;

    @TableField(value = "created_at", fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
