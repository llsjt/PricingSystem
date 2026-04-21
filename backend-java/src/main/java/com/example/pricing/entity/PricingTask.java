package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
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
    private BigDecimal currentPrice;

    @TableField("baseline_profit")
    private BigDecimal baselineProfit;

    @TableField("suggested_min_price")
    private BigDecimal suggestedMinPrice;

    @TableField("suggested_max_price")
    private BigDecimal suggestedMaxPrice;

    @TableField("strategy_goal")
    private String strategyGoal;

    @TableField("constraint_text")
    private String constraintText;

    @TableField("task_status")
    private String taskStatus;

    @TableField("requested_by_user_id")
    private Long requestedByUserId;

    @TableField("trace_id")
    private String traceId;

    @TableField("idempotency_key")
    private String idempotencyKey;

    @TableField("retry_count")
    private Integer retryCount;

    @TableField("consumer_retry_count")
    private Integer consumerRetryCount;

    @TableField("current_execution_id")
    private String currentExecutionId;

    @TableField("failure_reason")
    private String failureReason;

    @TableField("started_at")
    private LocalDateTime startedAt;

    @TableField("completed_at")
    private LocalDateTime completedAt;

    @TableField("llm_api_key_enc")
    private String llmApiKeyEnc;

    @TableField("llm_base_url")
    private String llmBaseUrl;

    @TableField("llm_model")
    private String llmModel;

    @TableField(exist = false)
    private String productTitle;

    @TableField(value = "created_at", fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(value = "updated_at", fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
