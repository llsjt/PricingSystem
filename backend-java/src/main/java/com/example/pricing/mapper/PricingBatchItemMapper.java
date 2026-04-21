package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.PricingBatchItem;
import org.apache.ibatis.annotations.Mapper;

/**
 * 批量任务子项 Mapper，负责 pricing_batch_item 表的数据访问。
 */
@Mapper
public interface PricingBatchItemMapper extends BaseMapper<PricingBatchItem> {
}
