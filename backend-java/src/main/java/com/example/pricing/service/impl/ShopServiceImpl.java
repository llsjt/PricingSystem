/*
 * 店铺服务实现，负责店铺增删改查和用户授权店铺查询。
 */

package com.example.pricing.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.dto.ShopCreateDTO;
import com.example.pricing.dto.ShopUpdateDTO;
import com.example.pricing.entity.Product;
import com.example.pricing.entity.Shop;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.mapper.ShopMapper;
import com.example.pricing.service.ShopService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 店铺管理服务实现。
 */
@Service
@RequiredArgsConstructor
public class ShopServiceImpl implements ShopService {

    private final ShopMapper shopMapper;
    private final ProductMapper productMapper;

    @Override
    public List<Shop> listByUser(Long userId) {
        LambdaQueryWrapper<Shop> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Shop::getUserId, userId).orderByDesc(Shop::getCreatedAt);
        return shopMapper.selectList(wrapper);
    }

    @Override
    public Shop create(Long userId, ShopCreateDTO dto) {
        if (dto.getShopName() == null || dto.getShopName().isBlank()) {
            throw new IllegalArgumentException("店铺名称不能为空");
        }
        if (dto.getPlatform() == null || dto.getPlatform().isBlank()) {
            throw new IllegalArgumentException("平台不能为空");
        }
        Shop shop = new Shop();
        shop.setUserId(userId);
        shop.setShopName(dto.getShopName().trim());
        shop.setPlatform(dto.getPlatform().trim());
        shop.setSellerNick(dto.getSellerNick() == null ? null : dto.getSellerNick().trim());
        shopMapper.insert(shop);
        return shop;
    }

    @Override
    public Shop update(Long shopId, Long userId, ShopUpdateDTO dto) {
        Shop shop = shopMapper.selectById(shopId);
        if (shop == null || !shop.getUserId().equals(userId)) {
            throw new IllegalArgumentException("店铺不存在或无权操作");
        }
        if (dto.getShopName() != null && !dto.getShopName().isBlank()) {
            shop.setShopName(dto.getShopName().trim());
        }
        if (dto.getPlatform() != null && !dto.getPlatform().isBlank()) {
            shop.setPlatform(dto.getPlatform().trim());
        }
        if (dto.getSellerNick() != null) {
            shop.setSellerNick(dto.getSellerNick().trim());
        }
        shopMapper.updateById(shop);
        return shop;
    }

    @Override
    public void delete(Long shopId, Long userId) {
        Shop shop = shopMapper.selectById(shopId);
        if (shop == null || !shop.getUserId().equals(userId)) {
            throw new IllegalArgumentException("店铺不存在或无权操作");
        }
        LambdaQueryWrapper<Product> productWrapper = new LambdaQueryWrapper<>();
        productWrapper.eq(Product::getShopId, shopId);
        long productCount = productMapper.selectCount(productWrapper);
        if (productCount > 0) {
            throw new IllegalArgumentException("该店铺下还有 " + productCount + " 个商品，请先删除商品");
        }
        shopMapper.deleteById(shopId);
    }

    @Override
    public List<Long> getShopIdsByUser(Long userId) {
        LambdaQueryWrapper<Shop> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Shop::getUserId, userId).select(Shop::getId);
        return shopMapper.selectList(wrapper).stream().map(Shop::getId).toList();
    }
}
