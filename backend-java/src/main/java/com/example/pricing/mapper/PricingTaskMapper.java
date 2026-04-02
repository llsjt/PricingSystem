package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.PricingTask;
import org.apache.ibatis.annotations.Mapper;

/**
 * 定价任务 Mapper，负责任务主表的增删改查。
 */
@Mapper
public interface PricingTaskMapper extends BaseMapper<PricingTask> {
}
