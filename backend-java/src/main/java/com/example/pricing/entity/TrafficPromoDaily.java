package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@TableName("traffic_promo_daily")
public class TrafficPromoDaily {
    @TableId(type = IdType.AUTO)
    private Long id;

    private Long shopId;

    private Long productId;

    private LocalDate statDate;

    private String trafficSource;

    private Integer impressionCount;

    private Integer clickCount;

    private Integer visitorCount;

    private BigDecimal costAmount;

    private BigDecimal payAmount;

    private BigDecimal roi;

    private Long uploadBatchId;

    private LocalDateTime createdAt;
}
