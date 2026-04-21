/*
 * 导入批次实体，对应一次商品或报表导入任务。
 */

package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 导入批次实体，记录一次 Excel 导入任务的文件、时间范围和执行结果。
 */
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
    private LocalDate startDate;

    @TableField("end_date")
    private LocalDate endDate;

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
