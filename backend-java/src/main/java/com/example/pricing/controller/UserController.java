package com.example.pricing.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.JwtUtil;
import com.example.pricing.common.Result;
import com.example.pricing.entity.SysUser;
import com.example.pricing.exception.ForbiddenException;
import com.example.pricing.exception.UnauthorizedException;
import com.example.pricing.mapper.SysUserMapper;
import com.example.pricing.security.AuthSessionService;
import com.example.pricing.security.LoginAttemptService;
import com.example.pricing.security.LoginAuditService;
import com.example.pricing.security.PasswordPolicyValidator;
import com.example.pricing.vo.UserListVO;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.mindrot.jbcrypt.BCrypt;
import org.springframework.http.HttpStatus;
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

@RestController
@RequestMapping("/api/user")
@RequiredArgsConstructor
public class UserController {

    private static final String ROLE_ADMIN = "ADMIN";
    private static final String ROLE_USER = "USER";

    private final SysUserMapper userMapper;
    private final JwtUtil jwtUtil;
    private final AuthSessionService authSessionService;
    private final LoginAttemptService loginAttemptService;
    private final LoginAuditService loginAuditService;

    @PostMapping("/login")
    public Result<Map<String, Object>> login(
            @RequestBody Map<String, String> body,
            HttpServletRequest request,
            HttpServletResponse response) {
        String username = trimToEmpty(body.get("username"));
        String password = body.getOrDefault("password", "");
        String attemptKey = buildAttemptKey(username, request);

        if (!loginAttemptService.isAllowed(attemptKey)) {
            loginAuditService.record(null, username, request, "BLOCKED", loginAttemptService.blockedMessage());
            return Result.error(HttpStatus.TOO_MANY_REQUESTS.value(), loginAttemptService.blockedMessage());
        }

        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.and(query -> query.eq(SysUser::getUsername, username).or().eq(SysUser::getAccount, username));
        SysUser user = userMapper.selectOne(wrapper);
        if (user == null || (user.getStatus() != null && user.getStatus() == 0)) {
            loginAttemptService.recordFailure(attemptKey);
            loginAuditService.record(null, username, request, "FAILED", "invalid credentials");
            return Result.error("Invalid username or password");
        }

        if (!BCrypt.checkpw(password, user.getPassword())) {
            loginAttemptService.recordFailure(attemptKey);
            loginAuditService.record(user.getId(), user.getUsername(), request, "FAILED", "invalid credentials");
            return Result.error("Invalid username or password");
        }

        loginAttemptService.recordSuccess(attemptKey);
        loginAuditService.record(user.getId(), user.getUsername(), request, "SUCCESS", null);
        return Result.success(buildSessionPayload(user, request, response));
    }

    @PostMapping("/refresh")
    public Result<Map<String, Object>> refresh(HttpServletRequest request, HttpServletResponse response) {
        AuthSessionService.IssuedSession issuedSession = authSessionService.rotate(request);
        SysUser user = userMapper.selectById(issuedSession.userId());
        if (user == null || (user.getStatus() != null && user.getStatus() == 0)) {
            authSessionService.clearRefreshCookie(response);
            throw new UnauthorizedException("Session expired, please log in again");
        }
        authSessionService.writeRefreshCookie(response, issuedSession.rawToken());
        return Result.success(buildAccessTokenPayload(user));
    }

    @PostMapping("/logout")
    public Result<Void> logout(HttpServletRequest request, HttpServletResponse response) {
        Long currentUserId = (Long) request.getAttribute("currentUserId");
        if (currentUserId != null) {
            SysUser user = userMapper.selectById(currentUserId);
            if (user != null) {
                user.setTokenVersion((user.getTokenVersion() == null ? 0 : user.getTokenVersion()) + 1);
                userMapper.updateById(user);
            }
        }
        authSessionService.revoke(request);
        authSessionService.clearRefreshCookie(response);
        return Result.success(null);
    }

    @GetMapping("/list")
    public Result<Page<UserListVO>> getUserList(
            HttpServletRequest request,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        requireAdmin(request);
        Page<SysUser> userPage = userMapper.selectPage(new Page<>(page, size), null);
        Page<UserListVO> resultPage = new Page<>();
        resultPage.setCurrent(userPage.getCurrent());
        resultPage.setSize(userPage.getSize());
        resultPage.setTotal(userPage.getTotal());
        resultPage.setRecords(userPage.getRecords().stream().map(this::toUserListVO).toList());
        return Result.success(resultPage);
    }

    @PostMapping("/add")
    public Result<Void> addUser(HttpServletRequest request, @RequestBody SysUser user) {
        requireAdmin(request);

        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(SysUser::getUsername, user.getUsername());
        if (userMapper.exists(wrapper)) {
            return Result.error("Username already exists");
        }

        PasswordPolicyValidator.validate(user.getPassword());
        user.setAccount(user.getUsername());
        user.setRole(normalizeRole(user.getRole()));
        user.setTokenVersion(0);
        user.setPassword(BCrypt.hashpw(user.getPassword(), BCrypt.gensalt()));
        user.setStatus(user.getStatus() == null ? 1 : user.getStatus());
        userMapper.insert(user);
        return Result.success(null);
    }

    @PutMapping("/{id}")
    public Result<Void> updateUser(HttpServletRequest request, @PathVariable Long id, @RequestBody SysUser user) {
        requireAdmin(request);

        SysUser existing = userMapper.selectById(id);
        if (existing == null) {
            return Result.error("User not found");
        }

        if (user.getUsername() != null && !user.getUsername().equals(existing.getUsername())) {
            LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(SysUser::getUsername, user.getUsername());
            if (userMapper.exists(wrapper)) {
                return Result.error("Username already exists");
            }
            existing.setUsername(user.getUsername());
            existing.setAccount(user.getUsername());
        }

        boolean invalidateToken = false;
        if (user.getPassword() != null && !user.getPassword().isBlank()) {
            PasswordPolicyValidator.validate(user.getPassword());
            existing.setPassword(BCrypt.hashpw(user.getPassword(), BCrypt.gensalt()));
            invalidateToken = true;
        }
        existing.setEmail(user.getEmail());
        if (user.getStatus() != null) {
            existing.setStatus(user.getStatus());
            invalidateToken = true;
        }
        if (user.getRole() != null && !user.getRole().isBlank()) {
            existing.setRole(normalizeRole(user.getRole()));
            invalidateToken = true;
        }
        if (invalidateToken) {
            existing.setTokenVersion((existing.getTokenVersion() == null ? 0 : existing.getTokenVersion()) + 1);
        }

        userMapper.updateById(existing);
        return Result.success(null);
    }

    @DeleteMapping("/{id:\\d+}")
    public Result<Void> deleteUser(HttpServletRequest request, @PathVariable Long id) {
        requireAdmin(request);

        SysUser existing = userMapper.selectById(id);
        if (existing != null && ROLE_ADMIN.equalsIgnoreCase(existing.getRole())) {
            return Result.error("Admin user cannot be deleted");
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
            return Result.error("Please select users to delete");
        }

        List<SysUser> users = userMapper.selectBatchIds(ids);
        boolean containsAdmin = users.stream().anyMatch(user -> ROLE_ADMIN.equalsIgnoreCase(user.getRole()));
        if (containsAdmin) {
            return Result.error("Admin user cannot be deleted");
        }

        userMapper.deleteBatchIds(ids);
        return Result.success(null);
    }

    private void requireAdmin(HttpServletRequest request) {
        String currentUsername = (String) request.getAttribute("currentUsername");
        if (currentUsername == null || currentUsername.isBlank()) {
            throw new UnauthorizedException("Please log in");
        }

        Boolean isAdmin = (Boolean) request.getAttribute("isAdmin");
        if (Boolean.TRUE.equals(isAdmin)) {
            return;
        }

        throw new ForbiddenException("Admin permission required");
    }

    private UserListVO toUserListVO(SysUser user) {
        UserListVO vo = new UserListVO();
        vo.setId(user.getId());
        vo.setUsername(user.getUsername());
        vo.setEmail(user.getEmail());
        vo.setStatus(user.getStatus());
        vo.setRole(normalizeRole(user.getRole()));
        vo.setCreatedAt(user.getCreatedAt());
        vo.setUpdatedAt(user.getUpdatedAt());
        return vo;
    }

    private Map<String, Object> buildSessionPayload(SysUser user, HttpServletRequest request, HttpServletResponse response) {
        AuthSessionService.IssuedSession issuedSession = authSessionService.issueSession(user.getId(), request);
        authSessionService.writeRefreshCookie(response, issuedSession.rawToken());
        return buildAccessTokenPayload(user);
    }

    private Map<String, Object> buildAccessTokenPayload(SysUser user) {
        String role = normalizeRole(user.getRole());
        String token = jwtUtil.generateAccessToken(
                user.getId(),
                user.getUsername(),
                role,
                user.getTokenVersion() == null ? 0 : user.getTokenVersion()
        );

        Map<String, Object> data = new HashMap<>();
        data.put("token", token);
        data.put("username", user.getUsername());
        data.put("role", role);
        data.put("isAdmin", ROLE_ADMIN.equalsIgnoreCase(role));
        return data;
    }

    private String normalizeRole(String role) {
        String normalized = trimToEmpty(role).toUpperCase();
        if (normalized.isBlank()) {
            return ROLE_USER;
        }
        if (!ROLE_ADMIN.equals(normalized) && !ROLE_USER.equals(normalized)) {
            throw new IllegalArgumentException("Invalid user role");
        }
        return normalized;
    }

    private String trimToEmpty(String value) {
        return value == null ? "" : value.trim();
    }

    private String buildAttemptKey(String username, HttpServletRequest request) {
        String forwardedFor = request.getHeader("X-Forwarded-For");
        String ipAddress = forwardedFor != null && !forwardedFor.isBlank()
                ? forwardedFor.split(",")[0].trim()
                : request.getRemoteAddr();
        return trimToEmpty(username).toLowerCase() + "|" + trimToEmpty(ipAddress);
    }
}
