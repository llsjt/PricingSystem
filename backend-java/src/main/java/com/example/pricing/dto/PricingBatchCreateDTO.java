package com.example.pricing.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.List;

@Data
public class PricingBatchCreateDTO {
    @NotEmpty(message = "至少选择一个商品")
    @Size(max = 50, message = "单批最多支持 50 个商品")
    private List<Long> productIds;

    @NotBlank(message = "策略目标不能为空")
    @Size(max = 50, message = "策略目标长度不能超过 50")
    private String strategyGoal;

    @Size(max = 1000, message = "约束条件长度不能超过 1000")
    private String constraints;
}
