package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("dec_task")
public class DecTask {
    @TableId(type = IdType.AUTO)
    private Long id;

    private String taskNo;

    private String strategyType;

    private String constraints; // JSON string

    private String productNames; // Snapshot of product names

    private String status; // PENDING, RUNNING, COMPLETED, FAILED

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
