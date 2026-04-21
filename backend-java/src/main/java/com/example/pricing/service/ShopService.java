/*
 * 店铺服务接口，定义店铺管理和用户店铺关联查询能力。
 */

package com.example.pricing.service;

import com.example.pricing.dto.ShopCreateDTO;
import com.example.pricing.dto.ShopUpdateDTO;
import com.example.pricing.entity.Shop;

import java.util.List;

/**
 * 店铺管理服务接口。
 */
public interface ShopService {

    /**
     * 查询用户的店铺列表。
     */
    List<Shop> listByUser(Long userId);

    /**
     * 创建店铺。
     */
    Shop create(Long userId, ShopCreateDTO dto);

    /**
     * 更新店铺（校验归属）。
     */
    Shop update(Long shopId, Long userId, ShopUpdateDTO dto);

    /**
     * 删除店铺（校验归属和关联商品）。
     */
    void delete(Long shopId, Long userId);

    /**
     * 获取用户拥有的所有店铺 ID。
     */
    List<Long> getShopIdsByUser(Long userId);
}
