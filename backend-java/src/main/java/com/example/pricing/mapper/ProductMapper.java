package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.Product;
import org.apache.ibatis.annotations.Mapper;

/**
 * 商品主表 Mapper，负责商品基础信息的读写。
 */
@Mapper
public interface ProductMapper extends BaseMapper<Product> {
}
