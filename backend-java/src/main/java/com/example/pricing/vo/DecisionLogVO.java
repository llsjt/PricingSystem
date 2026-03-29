package com.example.pricing.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Data
public class DecisionLogVO {
    private Long id;
    private Long taskId;
    private String roleName;
    private Integer speakOrder;
    private String thoughtContent;

    // Legacy compatibility fields for existing frontend consumption.
    private String agentCode;
    private String agentName;
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
