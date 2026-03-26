package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("agent_run_log")
public class DecAgentLog {
    @TableId(type = IdType.AUTO)
    private Long id;

    private Long taskId;

    private String agentCode;

    private String agentName;

    private Integer runOrder;

    private String runStatus;

    private String inputSummary;

    private String outputSummary;

    private String outputPayload;

    private java.math.BigDecimal suggestedPrice;

    private java.math.BigDecimal predictedProfit;

    private java.math.BigDecimal confidenceScore;

    private String riskLevel;

    private Integer needManualReview;

    private String errorMessage;

    @TableField(exist = false)
    private String roleName;

    @TableField(exist = false)
    private Integer speakOrder;

    @TableField(exist = false)
    private String thoughtContent;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
