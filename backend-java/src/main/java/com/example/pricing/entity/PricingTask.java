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
 * 定价任务实体，记录一次价格分析任务的输入商品、状态和建议区间。
 */
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
    private BigDecimal currentPrice;

    @TableField("baseline_profit")
    private BigDecimal baselineProfit;

    @TableField("suggested_min_price")
    private BigDecimal suggestedMinPrice;

    @TableField("suggested_max_price")
    private BigDecimal suggestedMaxPrice;

    @TableField("task_status")
    private String taskStatus;

    @TableField(exist = false)
    private String productTitle;

    @TableField(value = "created_at", fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(value = "updated_at", fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
