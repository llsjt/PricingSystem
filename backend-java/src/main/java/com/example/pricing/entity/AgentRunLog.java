package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("agent_run_log")
public class AgentRunLog {
    @TableId(type = IdType.AUTO)
    private Long id;

    @TableField("task_id")
    private Long taskId;

    @TableField("agent_code")
    private String agentCode;

    @TableField("agent_name")
    private String agentName;

    @TableField("run_order")
    private Integer runOrder;

    @TableField("run_status")
    private String runStatus;

    @TableField("input_summary")
    private String inputSummary;

    @TableField("output_summary")
    private String outputSummary;

    @TableField("output_payload")
    private String outputPayload;

    @TableField("suggested_price")
    private java.math.BigDecimal suggestedPrice;

    @TableField("predicted_profit")
    private java.math.BigDecimal predictedProfit;

    @TableField("confidence_score")
    private java.math.BigDecimal confidenceScore;

    @TableField("risk_level")
    private String riskLevel;

    @TableField("need_manual_review")
    private Integer needManualReview;

    @TableField("error_message")
    private String errorMessage;

    @TableField(exist = false)
    private String roleName;

    @TableField(exist = false)
    private Integer speakOrder;

    @TableField(exist = false)
    private String thoughtContent;

    @TableField(value = "created_at", fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
