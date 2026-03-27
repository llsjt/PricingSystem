package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("pricing_task")
public class PricingTask {
    @TableId(type = IdType.AUTO)
    private Long id;

    @TableField("task_code")
    private String taskCode;

    @TableField("shop_id")
    private Long shopId;

    @TableField("product_id")
    private Long productId;

    @TableField("sku_id")
    private Long skuId;

    @TableField("current_price")
    private java.math.BigDecimal currentPrice;

    @TableField("baseline_profit")
    private java.math.BigDecimal baselineProfit;

    @TableField("suggested_min_price")
    private java.math.BigDecimal suggestedMinPrice;

    @TableField("suggested_max_price")
    private java.math.BigDecimal suggestedMaxPrice;

    @TableField("task_status")
    private String taskStatus;

    @TableField(exist = false)
    private String productTitle;

    @TableField(value = "created_at", fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(value = "updated_at", fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
