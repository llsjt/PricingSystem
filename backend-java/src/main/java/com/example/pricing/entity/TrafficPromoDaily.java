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
@TableName("traffic_promo_daily")
public class TrafficPromoDaily {
    @TableId(type = IdType.AUTO)
    private Long id;

    @TableField("shop_id")
    private Long shopId;

    @TableField("product_id")
    private Long productId;

    @TableField("stat_date")
    private LocalDate statDate;

    @TableField("traffic_source")
    private String trafficSource;

    @TableField("impression_count")
    private Integer impressionCount;

    @TableField("click_count")
    private Integer clickCount;

    @TableField("visitor_count")
    private Integer visitorCount;

    @TableField("cost_amount")
    private BigDecimal costAmount;

    @TableField("pay_amount")
    private BigDecimal payAmount;

    @TableField("roi")
    private BigDecimal roi;

    @TableField("upload_batch_id")
    private Long uploadBatchId;

    @TableField(value = "created_at", fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
