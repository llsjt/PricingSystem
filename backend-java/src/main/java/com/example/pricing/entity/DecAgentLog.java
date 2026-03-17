package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("dec_agent_log")
public class DecAgentLog {
    @TableId(type = IdType.AUTO)
    private Long id;

    private Long taskId;

    private String roleName;

    private Integer speakOrder;

    private String thoughtContent;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
