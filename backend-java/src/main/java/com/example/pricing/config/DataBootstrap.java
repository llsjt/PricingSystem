package com.example.pricing.config;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.entity.Shop;
import com.example.pricing.entity.SysUser;
import com.example.pricing.mapper.ShopMapper;
import com.example.pricing.mapper.SysUserMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.mindrot.jbcrypt.BCrypt;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 系统启动后的基础数据初始化器，用于补齐管理员、默认店铺和密码迁移。
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class DataBootstrap {

    private final SysUserMapper userMapper;
    private final ShopMapper shopMapper;

    /**
     * 应用启动完成后执行初始化流程。
     */
    @jakarta.annotation.PostConstruct
    public void initialize() {
        SysUser admin = ensureAdminUser();
        ensureDefaultShop(admin.getId());
        migratePasswords();
    }

    /**
     * 确保系统中始终存在管理员账号，便于首次登录和系统管理。
     */
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
        admin.setPassword(BCrypt.hashpw("123456", BCrypt.gensalt()));
        admin.setEmail("admin@example.com");
        admin.setStatus(1);
        userMapper.insert(admin);
        log.info("初始化管理员账号：admin");
        return admin;
    }

    /**
     * 将库中历史明文密码迁移为 BCrypt 哈希，避免继续以不安全形式存储。
     */
    private void migratePasswords() {
        List<SysUser> users = userMapper.selectList(null);
        int migrated = 0;
        for (SysUser user : users) {
            String pwd = user.getPassword();
            if (pwd != null && !pwd.startsWith("$2a$") && !pwd.startsWith("$2b$")) {
                user.setPassword(BCrypt.hashpw(pwd, BCrypt.gensalt()));
                userMapper.updateById(user);
                migrated++;
            }
        }
        if (migrated > 0) {
            log.info("已将 {} 个用户的明文密码迁移为 BCrypt 哈希", migrated);
        }
    }

    /**
     * 为管理员补齐默认店铺，保证导入、商品管理等功能可直接使用。
     */
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
