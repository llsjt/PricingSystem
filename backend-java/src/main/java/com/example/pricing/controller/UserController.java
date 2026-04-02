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
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 用户管理控制器，处理登录、登出以及管理员的用户维护操作。
 */
@RestController
@RequestMapping("/api/user")
@RequiredArgsConstructor
public class UserController {

    private final SysUserMapper userMapper;
    private final JwtUtil jwtUtil;

    /**
     * 校验账号密码并签发 JWT，返回前端会话所需信息。
     */
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

    /**
     * 退出登录接口，当前由前端自行删除令牌，因此后端只返回成功状态。
     */
    @PostMapping("/logout")
    public Result<Void> logout() {
        return Result.success(null);
    }

    /**
     * 管理员分页查询系统用户列表。
     */
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

    /**
     * 管理员新增用户，并在落库前完成密码加密。
     */
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

    /**
     * 管理员更新用户资料，可选修改用户名、密码、邮箱和状态。
     */
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

    /**
     * 管理员删除单个用户，但保护内置管理员账号不被误删。
     */
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

    /**
     * 管理员批量删除用户，同样禁止删除管理员账号。
     */
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

    /**
     * 校验当前请求是否由管理员发起，不满足条件时抛出权限异常。
     */
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

    /**
     * 将用户实体转换为列表页展示对象，避免前端接收到敏感字段。
     */
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
