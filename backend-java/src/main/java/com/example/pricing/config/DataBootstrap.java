package com.example.pricing.config;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.entity.Shop;
import com.example.pricing.entity.SysUser;
import com.example.pricing.mapper.ShopMapper;
import com.example.pricing.mapper.SysUserMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class DataBootstrap {

    private final SysUserMapper userMapper;
    private final ShopMapper shopMapper;

    @jakarta.annotation.PostConstruct
    public void initialize() {
        SysUser admin = ensureAdminUser();
        ensureDefaultShop(admin.getId());
    }

    private SysUser ensureAdminUser() {
        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(SysUser::getAccount, "admin");
        SysUser admin = userMapper.selectOne(wrapper);
        if (admin != null) {
            return admin;
        }

        admin = new SysUser();
        admin.setUsername("admin");
        admin.setAccount("admin");
        admin.setPassword("123456");
        admin.setEmail("admin@example.com");
        admin.setStatus(1);
        userMapper.insert(admin);
        log.info("初始化管理员账号：admin");
        return admin;
    }

    private void ensureDefaultShop(Long userId) {
        LambdaQueryWrapper<Shop> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Shop::getUserId, userId).last("LIMIT 1");
        Shop shop = shopMapper.selectOne(wrapper);
        if (shop != null) {
            return;
        }

        shop = new Shop();
        shop.setUserId(userId);
        shop.setShopName("默认店铺");
        shop.setPlatform("淘宝");
        shop.setSellerNick("admin_shop");
        shopMapper.insert(shop);
        log.info("初始化默认店铺：{}", shop.getShopName());
    }
}
