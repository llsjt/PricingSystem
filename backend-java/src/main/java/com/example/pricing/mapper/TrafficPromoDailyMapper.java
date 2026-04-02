package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.TrafficPromoDaily;
import org.apache.ibatis.annotations.Mapper;

/**
 * 流量推广日报 Mapper，负责投放与流量效果数据的读写。
 */
@Mapper
public interface TrafficPromoDailyMapper extends BaseMapper<TrafficPromoDaily> {
}
