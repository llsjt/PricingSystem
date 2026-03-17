package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("sys_import_batch")
public class SysImportBatch {
    @TableId(type = IdType.AUTO)
    private Long id;

    private String batchNo;

    private String fileName;

    private Integer successCount;

    private Integer failCount;

    private String errorLog;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
