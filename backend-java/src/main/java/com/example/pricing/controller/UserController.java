package com.example.pricing.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.entity.SysUser;
import com.example.pricing.mapper.SysUserMapper;
import com.example.pricing.vo.UserListVO;
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

    @PostMapping("/login")
    public Result<Map<String, Object>> login(@RequestBody Map<String, String> body) {
        String username = body.get("username");
        String password = body.get("password");

        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.and(query -> query.eq(SysUser::getUsername, username).or().eq(SysUser::getAccount, username));
        SysUser user = userMapper.selectOne(wrapper);

        if (user == null || user.getStatus() != null && user.getStatus() == 0 || !user.getPassword().equals(password)) {
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
    public Result<Page<UserListVO>> getUserList(
            @RequestHeader(value = "X-Username", required = false) String currentUsername,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        requireAdmin(currentUsername);
        Page<SysUser> pageParam = new Page<>(page, size);
        Page<SysUser> userPage = userMapper.selectPage(pageParam, null);
        Page<UserListVO> resultPage = new Page<>();
        resultPage.setCurrent(userPage.getCurrent());
        resultPage.setSize(userPage.getSize());
        resultPage.setTotal(userPage.getTotal());
        resultPage.setRecords(userPage.getRecords().stream().map(this::toUserListVO).toList());
        return Result.success(resultPage);
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

        user.setAccount(user.getUsername());
        user.setStatus(user.getStatus() == null ? 1 : user.getStatus());
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
            existing.setAccount(user.getUsername());
        }

        if (user.getPassword() != null && !user.getPassword().isBlank()) {
            existing.setPassword(user.getPassword());
        }
        existing.setEmail(user.getEmail());
        if (user.getStatus() != null) {
            existing.setStatus(user.getStatus());
        }

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
        wrapper.and(query -> query.eq(SysUser::getUsername, currentUsername).or().eq(SysUser::getAccount, currentUsername));
        SysUser user = userMapper.selectOne(wrapper);

        if (user == null || !"admin".equals(user.getUsername())) {
            throw new RuntimeException("无权进行此操作，仅限管理员");
        }
    }

    private UserListVO toUserListVO(SysUser user) {
        UserListVO vo = new UserListVO();
        vo.setId(user.getId());
        vo.setUsername(user.getUsername());
        vo.setEmail(user.getEmail());
        vo.setStatus(user.getStatus());
        vo.setCreatedAt(user.getCreatedAt());
        vo.setUpdatedAt(user.getUpdatedAt());
        return vo;
    }
}
