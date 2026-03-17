package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("dec_result")
public class DecResult {
    @TableId(type = IdType.AUTO)
    private Long id;

    private Long taskId;

    private Long productId;

    private BigDecimal suggestedPrice;

    private BigDecimal profitChange;

    private BigDecimal discountRate;

    private String coreReasons;

    private Boolean isAccepted;

    private String adoptStatus;

    private String rejectReason;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
