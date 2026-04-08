package com.example.pricing.common;

import com.example.pricing.entity.SysUser;
import com.example.pricing.mapper.SysUserMapper;
import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.io.IOException;

@Component
@RequiredArgsConstructor
public class JwtAuthInterceptor implements HandlerInterceptor {

    private final JwtUtil jwtUtil;
    private final SysUserMapper userMapper;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws IOException {
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }

        String authHeader = request.getHeader("Authorization");
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            sendError(response, 401, "Please log in");
            return false;
        }

        String token = authHeader.substring(7);
        try {
            Claims claims = jwtUtil.parseAccessToken(token);
            Long userId = claims.get("userId", Long.class);
            SysUser currentUser = userId == null ? null : userMapper.selectById(userId);
            if (currentUser == null || (currentUser.getStatus() != null && currentUser.getStatus() == 0)) {
                sendError(response, 401, "Please log in");
                return false;
            }

            Integer tokenVersion = claims.get("tokenVersion", Integer.class);
            int currentTokenVersion = currentUser.getTokenVersion() == null ? 0 : currentUser.getTokenVersion();
            if ((tokenVersion == null ? 0 : tokenVersion) != currentTokenVersion) {
                sendError(response, 401, "Session expired, please log in again");
                return false;
            }

            String role = claims.get("role", String.class);
            if (role == null || role.isBlank()) {
                role = currentUser.getRole();
            }
            request.setAttribute("currentUsername", currentUser.getUsername());
            request.setAttribute("currentUserId", currentUser.getId());
            request.setAttribute("currentUserRole", role);
            request.setAttribute("isAdmin", "ADMIN".equalsIgnoreCase(role));
            return true;
        } catch (Exception e) {
            sendError(response, 401, "Session expired, please log in again");
            return false;
        }
    }

    private void sendError(HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"code\":" + status + ",\"message\":\"" + message + "\",\"data\":null}");
    }
}
