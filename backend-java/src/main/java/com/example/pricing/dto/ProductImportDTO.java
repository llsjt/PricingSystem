package com.example.pricing.dto;

import com.alibaba.excel.annotation.ExcelProperty;
import lombok.Data;
import java.math.BigDecimal;

@Data
public class ProductImportDTO {
    @ExcelProperty("商品标题")
    private String title;

    @ExcelProperty("商品类别")
    private String category;

    @ExcelProperty("成本价")
    private BigDecimal costPrice;

    @ExcelProperty("市场价")
    private BigDecimal marketPrice;

    @ExcelProperty("当前售价")
    private BigDecimal currentPrice;

    @ExcelProperty("库存")
    private Integer stock;

    @ExcelProperty("月销售量")
    private Integer monthlySales;

    // Excel 中可能是 "12%" 或 "0.12"
    @ExcelProperty("点击率")
    private String clickRateStr;

    @ExcelProperty("转化率")
    private String conversionRateStr;

    @ExcelProperty("日销售量")
    private Integer dailySales;

    @ExcelProperty("日访客数")
    private Integer dailyVisitors;
}
