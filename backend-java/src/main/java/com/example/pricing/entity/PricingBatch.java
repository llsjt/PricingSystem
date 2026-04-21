package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 批量定价主任务实体，对应一次批量定价批次。
 */
@Data
@TableName("pricing_batch")
public class PricingBatch {
    @TableId(type = IdType.AUTO)
    private Long id;

    @TableField("batch_code")
    private String batchCode;

    @TableField("requested_by_user_id")
    private Long requestedByUserId;

    @TableField("strategy_goal")
    private String strategyGoal;

    @TableField("constraint_text")
    private String constraintText;

    @TableField("total_count")
    private Integer totalCount;

    @TableField("completed_count")
    private Integer completedCount;

    @TableField("manual_review_count")
    private Integer manualReviewCount;

    @TableField("failed_count")
    private Integer failedCount;

    @TableField("cancelled_count")
    private Integer cancelledCount;

    @TableField("batch_status")
    private String batchStatus;

    @TableField("finalized_at")
    private LocalDateTime finalizedAt;

    @TableField(value = "created_at", fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(value = "updated_at", fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
