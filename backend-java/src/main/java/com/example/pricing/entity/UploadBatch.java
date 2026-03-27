package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("upload_batch")
public class UploadBatch {
    @TableId(type = IdType.AUTO)
    private Long id;

    @TableField("shop_id")
    private Long shopId;

    @TableField("batch_no")
    private String batchNo;

    @TableField("file_name")
    private String fileName;

    @TableField("data_type")
    private String dataType;

    @TableField("start_date")
    private java.time.LocalDate startDate;

    @TableField("end_date")
    private java.time.LocalDate endDate;

    @TableField("row_count")
    private Integer rowCount;

    @TableField("success_count")
    private Integer successCount;

    @TableField("fail_count")
    private Integer failCount;

    @TableField("upload_status")
    private String uploadStatus;

    @TableField("uploaded_at")
    private LocalDateTime uploadedAt;
}
