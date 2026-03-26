package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("pricing_result")
public class DecResult {
    @TableId(type = IdType.AUTO)
    private Long id;

    private Long taskId;

    private BigDecimal finalPrice;

    private Integer expectedSales;

    private BigDecimal expectedProfit;

    private BigDecimal profitGrowth;

    private Integer isPass;

    private String executeStrategy;

    private String resultSummary;

    @TableField(exist = false)
    private Long productId;

    @TableField(exist = false)
    private String productTitle;

    @TableField(exist = false)
    private BigDecimal originalPrice;

    @TableField(exist = false)
    private Boolean applied;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
