package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.PricingResult;
import org.apache.ibatis.annotations.Mapper;

/**
 * 定价结果 Mapper，负责持久化最终价格建议及收益预测。
 */
@Mapper
public interface PricingResultMapper extends BaseMapper<PricingResult> {
}
