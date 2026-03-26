package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("pricing_task")
public class DecTask {
    @TableId(type = IdType.AUTO)
    private Long id;

    @TableField("task_code")
    private String taskCode;

    private Long shopId;

    private Long productId;

    private Long skuId;

    private java.math.BigDecimal currentPrice;

    private java.math.BigDecimal baselineProfit;

    private java.math.BigDecimal suggestedMinPrice;

    private java.math.BigDecimal suggestedMaxPrice;

    @TableField("task_status")
    private String taskStatus;

    @TableField(exist = false)
    private String productTitle;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
