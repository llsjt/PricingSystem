package com.example.pricing.config;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.entity.Shop;
import com.example.pricing.entity.SysUser;
import com.example.pricing.mapper.ShopMapper;
import com.example.pricing.mapper.SysUserMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.mindrot.jbcrypt.BCrypt;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 开发期数据引导器，按启动条件自动补齐本地演示数据。
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class DataBootstrap {

    private final SysUserMapper userMapper;
    private final ShopMapper shopMapper;

    @Value("${app.security.allow-dev-bootstrap:true}")
    private boolean allowDevBootstrap;

    @jakarta.annotation.PostConstruct
    public void initialize() {
        if (allowDevBootstrap) {
            SysUser admin = ensureAdminUser();
            ensureDefaultShop(admin.getId());
        }
        migratePasswordsAndRoles();
    }

    private SysUser ensureAdminUser() {
        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(SysUser::getAccount, "admin");
        SysUser admin = userMapper.selectOne(wrapper);
        if (admin != null) {
            boolean changed = false;
            if (!"ADMIN".equalsIgnoreCase(admin.getRole())) {
                admin.setRole("ADMIN");
                changed = true;
            }
            if (admin.getTokenVersion() == null) {
                admin.setTokenVersion(0);
                changed = true;
            }
            if (changed) {
                userMapper.updateById(admin);
            }
            return admin;
        }

        admin = new SysUser();
        admin.setUsername("admin");
        admin.setAccount("admin");
        admin.setPassword(BCrypt.hashpw("123456", BCrypt.gensalt()));
        admin.setEmail("admin@example.com");
        admin.setStatus(1);
        admin.setRole("ADMIN");
        admin.setTokenVersion(0);
        userMapper.insert(admin);
        log.info("Initialized development admin account");
        return admin;
    }

    private void migratePasswordsAndRoles() {
        List<SysUser> users = userMapper.selectList(null);
        int migrated = 0;
        for (SysUser user : users) {
            boolean changed = false;
            String pwd = user.getPassword();
            if (pwd != null && !pwd.startsWith("$2a$") && !pwd.startsWith("$2b$")) {
                user.setPassword(BCrypt.hashpw(pwd, BCrypt.gensalt()));
                changed = true;
            }

            String role = user.getRole();
            String normalizedRole = "admin".equalsIgnoreCase(user.getAccount()) || "admin".equalsIgnoreCase(user.getUsername())
                    ? "ADMIN"
                    : "USER";
            if (role == null || role.isBlank()) {
                user.setRole(normalizedRole);
                changed = true;
            }
            if (user.getTokenVersion() == null) {
                user.setTokenVersion(0);
                changed = true;
            }

            if (changed) {
                userMapper.updateById(user);
                migrated++;
            }
        }
        if (migrated > 0) {
            log.info("Migrated {} user records to hashed passwords and explicit roles", migrated);
        }
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
        log.info("Initialized development default shop");
    }
}
