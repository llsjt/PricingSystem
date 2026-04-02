package com.example.pricing.dto;

import lombok.Data;

import java.time.LocalDate;

/**
 * 模拟电商导出 Excel 的可视化生成参数。
 */
@Data
public class MockExcelExportDTO {
    private Integer productCount = 20;
    private Integer dailyCount = 120;
    private Integer skuCount = 60;
    private Integer trafficCount = 140;
    private Long startProductId;
    private LocalDate startDate;
    private Long seed = 20260402L;
}
