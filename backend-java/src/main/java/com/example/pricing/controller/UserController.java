package com.example.pricing.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.entity.SysUser;
import com.example.pricing.mapper.SysUserMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/user")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class UserController {

    private final SysUserMapper userMapper;

    @jakarta.annotation.PostConstruct
    public void initAdmin() {
        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(SysUser::getUsername, "admin");
        if (!userMapper.exists(wrapper)) {
            SysUser admin = new SysUser();
            admin.setUsername("admin");
            admin.setPassword("123456");
            admin.setEmail("admin@example.com");
            userMapper.insert(admin);
            System.out.println("Initialized admin user with password '123456'");
        }
    }

    @PostMapping("/login")
    public Result<Map<String, Object>> login(@RequestBody Map<String, String> body) {
        String username = body.get("username");
        String password = body.get("password");

        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(SysUser::getUsername, username);
        SysUser user = userMapper.selectOne(wrapper);

        if (user == null || !user.getPassword().equals(password)) {
            return Result.error("用户名或密码错误");
        }

        Map<String, Object> data = new HashMap<>();
        data.put("username", user.getUsername());
        data.put("isAdmin", "admin".equals(user.getUsername()));
        return Result.success(data);
    }

    @PostMapping("/logout")
    public Result<Void> logout() {
        return Result.success(null);
    }

    @GetMapping("/list")
    public Result<Page<SysUser>> getUserList(
            @RequestHeader(value = "X-Username", required = false) String currentUsername,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        requireAdmin(currentUsername);
        Page<SysUser> pageParam = new Page<>(page, size);
        return Result.success(userMapper.selectPage(pageParam, null));
    }

    @PostMapping("/add")
    public Result<Void> addUser(
            @RequestHeader(value = "X-Username", required = false) String currentUsername,
            @RequestBody SysUser user) {
        requireAdmin(currentUsername);

        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(SysUser::getUsername, user.getUsername());
        if (userMapper.exists(wrapper)) {
            return Result.error("用户名已存在");
        }

        userMapper.insert(user);
        return Result.success(null);
    }

    @PutMapping("/{id}")
    public Result<Void> updateUser(
            @RequestHeader(value = "X-Username", required = false) String currentUsername,
            @PathVariable Long id,
            @RequestBody SysUser user) {
        requireAdmin(currentUsername);

        SysUser existing = userMapper.selectById(id);
        if (existing == null) {
            return Result.error("用户不存在");
        }

        if (user.getUsername() != null && !user.getUsername().equals(existing.getUsername())) {
            LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(SysUser::getUsername, user.getUsername());
            if (userMapper.exists(wrapper)) {
                return Result.error("用户名已存在");
            }
            existing.setUsername(user.getUsername());
        }

        if (user.getPassword() != null && !user.getPassword().isBlank()) {
            existing.setPassword(user.getPassword());
        }
        existing.setEmail(user.getEmail());

        userMapper.updateById(existing);
        return Result.success(null);
    }

    @DeleteMapping("/{id:\\d+}")
    public Result<Void> deleteUser(
            @RequestHeader(value = "X-Username", required = false) String currentUsername,
            @PathVariable Long id) {
        requireAdmin(currentUsername);

        SysUser existing = userMapper.selectById(id);
        if (existing != null && "admin".equals(existing.getUsername())) {
            return Result.error("不能删除管理员");
        }

        userMapper.deleteById(id);
        return Result.success(null);
    }

    @DeleteMapping("/batch-delete")
    public Result<Void> batchDeleteUsers(
            @RequestHeader(value = "X-Username", required = false) String currentUsername,
            @RequestParam("ids") List<Long> ids) {
        requireAdmin(currentUsername);

        if (ids == null || ids.isEmpty()) {
            return Result.error("请选择要删除的用户");
        }

        List<SysUser> users = userMapper.selectBatchIds(ids);
        boolean containsAdmin = users.stream().anyMatch(user -> "admin".equals(user.getUsername()));
        if (containsAdmin) {
            return Result.error("不能删除管理员");
        }

        userMapper.deleteBatchIds(ids);
        return Result.success(null);
    }

    private void requireAdmin(String currentUsername) {
        if (currentUsername == null || currentUsername.isBlank()) {
            throw new RuntimeException("请先登录");
        }

        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(SysUser::getUsername, currentUsername);
        SysUser user = userMapper.selectOne(wrapper);

        if (user == null || !"admin".equals(user.getUsername())) {
            throw new RuntimeException("无权进行此操作，仅限管理员");
        }
    }
}
