package com.example.pricing.vo;

import com.alibaba.excel.annotation.ExcelIgnore;
import com.alibaba.excel.annotation.ExcelProperty;
import lombok.Data;
import java.math.BigDecimal;

@Data
public class DecisionComparisonVO {
    @ExcelIgnore
    private Long resultId;

    @ExcelProperty("商品ID")
    private Long productId;
    
    @ExcelProperty("商品标题")
    private String productTitle;
    
    @ExcelProperty("原价格")
    private BigDecimal originalPrice;
    
    @ExcelProperty("建议价格")
    private BigDecimal suggestedPrice;
    
    @ExcelProperty("原预估利润")
    private BigDecimal originalProfit;
    
    @ExcelProperty("新预估利润")
    private BigDecimal newProfit;

    @ExcelProperty("预计利润变化")
    private BigDecimal profitChange;

    @ExcelProperty("折扣率")
    private BigDecimal discountRate;

    @ExcelProperty("是否采纳")
    private Boolean isAccepted;

    @ExcelProperty("采纳状态")
    private String adoptStatus;

    @ExcelProperty("驳回原因")
    private String rejectReason;
}
