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
@TableName("biz_sales_daily")
public class BizProductDailyStat {
    @TableId(type = IdType.AUTO)
    private Long id;
    
    private Long productId;
    
    private LocalDate statDate;
    
    @TableField(exist = false)
    private Integer visitorCount;
    
    @TableField("daily_sales")
    private Integer salesCount;
    
    @TableField("daily_revenue")
    private BigDecimal turnover;
    
    @TableField(exist = false)
    private BigDecimal conversionRate;
    
    private LocalDateTime createdAt;
}
