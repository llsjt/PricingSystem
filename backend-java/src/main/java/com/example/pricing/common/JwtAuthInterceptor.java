package com.example.pricing.common;

import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.io.IOException;

/**
 * JWT 认证拦截器，用于校验接口请求中的登录令牌并写入当前用户上下文。
 */
@Component
@RequiredArgsConstructor
public class JwtAuthInterceptor implements HandlerInterceptor {

    private final JwtUtil jwtUtil;

    /**
     * 在请求进入控制器前校验 Bearer Token，认证通过后写入用户信息。
     */
    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws IOException {
        // 预检请求不参与认证校验，直接放行。
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }

        String authHeader = request.getHeader("Authorization");
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            sendError(response, 401, "请先登录");
            return false;
        }

        String token = authHeader.substring(7);
        try {
            Claims claims = jwtUtil.parseToken(token);
            request.setAttribute("currentUsername", claims.getSubject());
            request.setAttribute("currentUserId", claims.get("userId", Long.class));
            request.setAttribute("isAdmin", claims.get("isAdmin", Boolean.class));
            return true;
        } catch (Exception e) {
            sendError(response, 401, "登录已过期，请重新登录");
            return false;
        }
    }

    /**
     * 统一输出认证失败响应，避免拦截器内直接抛出未处理异常。
     */
    private void sendError(HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"code\":" + status + ",\"message\":\"" + message + "\",\"data\":null}");
    }
}
