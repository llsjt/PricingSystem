package com.example.pricing.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.JwtUtil;
import com.example.pricing.common.Result;
import com.example.pricing.entity.SysUser;
import com.example.pricing.exception.ForbiddenException;
import com.example.pricing.exception.UnauthorizedException;
import com.example.pricing.mapper.SysUserMapper;
import com.example.pricing.vo.UserListVO;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.mindrot.jbcrypt.BCrypt;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/user")
@RequiredArgsConstructor
public class UserController {

    private final SysUserMapper userMapper;
    private final JwtUtil jwtUtil;

    @PostMapping("/login")
    public Result<Map<String, Object>> login(@RequestBody Map<String, String> body) {
        String username = body.get("username");
        String password = body.get("password");

        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.and(query -> query.eq(SysUser::getUsername, username).or().eq(SysUser::getAccount, username));
        SysUser user = userMapper.selectOne(wrapper);

        if (user == null || user.getStatus() != null && user.getStatus() == 0) {
            return Result.error("用户名或密码错误");
        }

        if (!BCrypt.checkpw(password, user.getPassword())) {
            return Result.error("用户名或密码错误");
        }

        boolean isAdmin = "admin".equals(user.getUsername());
        String token = jwtUtil.generateToken(user.getId(), user.getUsername(), isAdmin);

        Map<String, Object> data = new HashMap<>();
        data.put("token", token);
        data.put("username", user.getUsername());
        data.put("isAdmin", isAdmin);
        return Result.success(data);
    }

    @PostMapping("/logout")
    public Result<Void> logout() {
        return Result.success(null);
    }

    @GetMapping("/list")
    public Result<Page<UserListVO>> getUserList(
            HttpServletRequest request,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        requireAdmin(request);
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
            HttpServletRequest request,
            @RequestBody SysUser user) {
        requireAdmin(request);

        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(SysUser::getUsername, user.getUsername());
        if (userMapper.exists(wrapper)) {
            return Result.error("用户名已存在");
        }

        user.setAccount(user.getUsername());
        user.setPassword(BCrypt.hashpw(user.getPassword(), BCrypt.gensalt()));
        user.setStatus(user.getStatus() == null ? 1 : user.getStatus());
        userMapper.insert(user);
        return Result.success(null);
    }

    @PutMapping("/{id}")
    public Result<Void> updateUser(
            HttpServletRequest request,
            @PathVariable Long id,
            @RequestBody SysUser user) {
        requireAdmin(request);

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
            existing.setPassword(BCrypt.hashpw(user.getPassword(), BCrypt.gensalt()));
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
            HttpServletRequest request,
            @PathVariable Long id) {
        requireAdmin(request);

        SysUser existing = userMapper.selectById(id);
        if (existing != null && "admin".equals(existing.getUsername())) {
            return Result.error("不能删除管理员");
        }

        userMapper.deleteById(id);
        return Result.success(null);
    }

    @DeleteMapping("/batch-delete")
    public Result<Void> batchDeleteUsers(
            HttpServletRequest request,
            @RequestParam("ids") List<Long> ids) {
        requireAdmin(request);

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

    private void requireAdmin(HttpServletRequest request) {
        String currentUsername = (String) request.getAttribute("currentUsername");
        if (currentUsername == null || currentUsername.isBlank()) {
            throw new UnauthorizedException("请先登录");
        }

        Boolean isAdmin = (Boolean) request.getAttribute("isAdmin");
        if (isAdmin != null && isAdmin) {
            return;
        }

        throw new ForbiddenException("无权进行此操作，仅限管理员");
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
