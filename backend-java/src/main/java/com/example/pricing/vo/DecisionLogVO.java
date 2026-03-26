package com.example.pricing.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class DecisionLogVO {
    private Long id;
    private String agentCode;
    private String agentName;
    private Integer runOrder;
    private String runStatus;
    private String outputSummary;
    private BigDecimal suggestedPrice;
    private BigDecimal predictedProfit;
    private BigDecimal confidenceScore;
    private String riskLevel;
    private Boolean needManualReview;
    private LocalDateTime createdAt;
}
