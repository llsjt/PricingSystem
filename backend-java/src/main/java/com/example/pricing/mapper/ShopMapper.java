package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.Shop;
import org.apache.ibatis.annotations.Mapper;

/**
 * 店铺 Mapper，负责查询和维护店铺基础信息。
 */
@Mapper
public interface ShopMapper extends BaseMapper<Shop> {
}
