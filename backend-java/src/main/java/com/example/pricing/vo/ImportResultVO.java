package com.example.pricing.vo;

import lombok.Data;

import java.time.LocalDate;
import java.util.List;

/**
 * 导入结果视图对象，反馈导入类型、成功失败数量和错误信息。
 */
@Data
public class ImportResultVO {
    private String dataType;
    private String dataTypeLabel;
    private String targetTable;
    private String fileName;
    private Integer rowCount;
    private Integer successCount;
    private Integer failCount;
    private String uploadStatus;
    private LocalDate startDate;
    private LocalDate endDate;
    private Boolean autoDetected;
    private String summary;
    private List<String> errors;
}
