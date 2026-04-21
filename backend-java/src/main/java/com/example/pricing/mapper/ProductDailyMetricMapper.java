/*
 * 商品日指标 Mapper，负责 product_daily_metric 表的数据访问。
 */

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
