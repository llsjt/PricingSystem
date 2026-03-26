package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("upload_batch")
public class SysImportBatch {
    @TableId(type = IdType.AUTO)
    private Long id;

    private Long shopId;

    private String batchNo;

    private String fileName;

    private String dataType;

    private java.time.LocalDate startDate;

    private java.time.LocalDate endDate;

    private Integer rowCount;

    private Integer successCount;

    private Integer failCount;

    private String uploadStatus;

    private LocalDateTime uploadedAt;
}
