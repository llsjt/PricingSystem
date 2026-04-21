package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.PricingBatch;
import org.apache.ibatis.annotations.Mapper;

/**
 * 批量任务主表 Mapper，负责 pricing_batch 表的数据访问。
 */
@Mapper
public interface PricingBatchMapper extends BaseMapper<PricingBatch> {
}
