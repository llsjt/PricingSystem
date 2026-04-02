package com.example.pricing.vo;

import com.alibaba.excel.annotation.ExcelIgnore;
import com.alibaba.excel.annotation.ExcelProperty;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 决策结果对比视图对象，用于页面展示和 Excel 导出。
 */
@Data
public class DecisionComparisonVO {
    @ExcelIgnore
    private Long resultId;

    @ExcelProperty("商品ID")
    private Long productId;

    @ExcelProperty("商品标题")
    private String productTitle;

    @ExcelProperty("原价")
    private BigDecimal originalPrice;

    @ExcelProperty("建议价格")
    private BigDecimal suggestedPrice;

    @ExcelProperty("预计利润变化")
    private BigDecimal profitChange;

    @ExcelProperty("预期销量")
    private Integer expectedSales;

    @ExcelProperty("预期利润")
    private BigDecimal expectedProfit;

    @ExcelProperty("风控结果")
    private String passStatus;

    @ExcelProperty("执行策略")
    private String executeStrategy;

    @ExcelProperty("结果说明")
    private String resultSummary;

    @ExcelProperty("是否已应用")
    private String appliedStatus;
}
