package com.example.pricing.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class TrafficPromoDailyVO {
    private Long id;
    private LocalDate statDate;
    private String trafficSource;
    private Integer impressionCount;
    private Integer clickCount;
    private Integer visitorCount;
    private BigDecimal costAmount;
    private BigDecimal payAmount;
    private BigDecimal roi;
    private LocalDateTime createdAt;
}
