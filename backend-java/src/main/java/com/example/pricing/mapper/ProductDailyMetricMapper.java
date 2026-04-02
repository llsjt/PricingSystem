package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.ProductDailyMetric;
import org.apache.ibatis.annotations.Mapper;

/**
 * 商品日指标 Mapper，负责经营日报数据的持久化。
 */
@Mapper
public interface ProductDailyMetricMapper extends BaseMapper<ProductDailyMetric> {
}
