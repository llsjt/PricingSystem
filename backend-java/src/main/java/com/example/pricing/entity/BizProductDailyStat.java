package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@TableName("product_daily_metric")
public class BizProductDailyStat {
    @TableId(type = IdType.AUTO)
    private Long id;

    private Long shopId;
    
    private Long productId;
    
    private LocalDate statDate;
    
    private Integer visitorCount;

    private Integer addCartCount;

    private Integer payBuyerCount;
    
    @TableField("pay_item_qty")
    private Integer salesCount;
    
    @TableField("pay_amount")
    private BigDecimal turnover;

    private BigDecimal refundAmount;
    
    @TableField("convert_rate")
    private BigDecimal conversionRate;

    private Long uploadBatchId;
    
    private LocalDateTime createdAt;
}
