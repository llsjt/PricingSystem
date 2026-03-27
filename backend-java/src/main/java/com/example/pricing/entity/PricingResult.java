package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("pricing_result")
public class PricingResult {
    @TableId(type = IdType.AUTO)
    private Long id;

    @TableField("task_id")
    private Long taskId;

    @TableField("final_price")
    private BigDecimal finalPrice;

    @TableField("expected_sales")
    private Integer expectedSales;

    @TableField("expected_profit")
    private BigDecimal expectedProfit;

    @TableField("profit_growth")
    private BigDecimal profitGrowth;

    @TableField("is_pass")
    private Integer isPass;

    @TableField("execute_strategy")
    private String executeStrategy;

    @TableField("result_summary")
    private String resultSummary;

    @TableField(exist = false)
    private Long productId;

    @TableField(exist = false)
    private String productTitle;

    @TableField(exist = false)
    private BigDecimal originalPrice;

    @TableField(exist = false)
    private Boolean applied;

    @TableField(value = "created_at", fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(value = "updated_at", fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
