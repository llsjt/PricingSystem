/*
 * 流量促销 Mapper，负责 traffic_promo_daily 表的数据访问。
 */

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
