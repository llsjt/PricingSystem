/*
 * 决策日志视图对象。
 */

package com.example.pricing.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 决策日志视图对象，用于展示多智能体分析过程和附带证据。
 */
@Data
public class DecisionLogVO {
    private Long id;
    private Long taskId;
    private String roleName;
    private Integer speakOrder;
    private String thoughtContent;

    /**
     * 兼容旧版前端字段命名，避免前后端联调时发生字段丢失。
     */
    private String agentCode;
    private String agentName;
    private Integer runAttempt;
    private Integer runOrder;
    private Integer displayOrder;
    private String stage;
    private String runStatus;
    private String outputSummary;
    private BigDecimal suggestedPrice;
    private BigDecimal predictedProfit;
    private BigDecimal confidenceScore;
    private String riskLevel;
    private Boolean needManualReview;
    private String thinking;
    private List<Map<String, Object>> evidence;
    private Map<String, Object> suggestion;
    private String reasonWhy;
    private LocalDateTime createdAt;
}
