/*
 * 商品 SKU Mapper，负责 product_sku 表的数据访问。
 */

package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.ProductSku;
import org.apache.ibatis.annotations.Mapper;

/**
 * 商品 SKU Mapper，负责规格层级数据的读写。
 */
@Mapper
public interface ProductSkuMapper extends BaseMapper<ProductSku> {
}
