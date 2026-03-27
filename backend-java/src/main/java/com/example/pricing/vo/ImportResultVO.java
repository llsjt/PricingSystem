package com.example.pricing.vo;

import lombok.Data;

import java.time.LocalDate;
import java.util.List;

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
