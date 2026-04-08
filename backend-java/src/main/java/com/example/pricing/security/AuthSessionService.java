package com.example.pricing.security;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.entity.AuthRefreshSession;
import com.example.pricing.exception.UnauthorizedException;
import com.example.pricing.mapper.AuthRefreshSessionMapper;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.util.HexFormat;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class AuthSessionService {

    public static final String REFRESH_COOKIE_NAME = "refresh_token";

    private final AuthRefreshSessionMapper authRefreshSessionMapper;

    @Value("${app.security.refresh-token-days:14}")
    private long refreshTokenDays;

    @Value("${app.security.secure-cookie:false}")
    private boolean secureCookie;

    public IssuedSession issueSession(Long userId, HttpServletRequest request) {
        String rawToken = UUID.randomUUID().toString().replace("-", "") + UUID.randomUUID().toString().replace("-", "");
        AuthRefreshSession session = new AuthRefreshSession();
        session.setUserId(userId);
        session.setTokenHash(hashToken(rawToken));
        session.setExpiresAt(LocalDateTime.now().plusDays(Math.max(refreshTokenDays, 1)));
        session.setLastUsedAt(LocalDateTime.now());
        session.setIpAddress(resolveClientIp(request));
        session.setUserAgent(truncate(request.getHeader("User-Agent"), 255));
        authRefreshSessionMapper.insert(session);
        return new IssuedSession(userId, rawToken);
    }

    public IssuedSession rotate(HttpServletRequest request) {
        String rawToken = readRefreshToken(request);
        AuthRefreshSession existing = getActiveSession(rawToken);
        existing.setRevokedAt(LocalDateTime.now());
        authRefreshSessionMapper.updateById(existing);
        return issueSession(existing.getUserId(), request);
    }

    public void revoke(HttpServletRequest request) {
        String rawToken = tryReadRefreshToken(request);
        if (rawToken == null || rawToken.isBlank()) {
            return;
        }
        LambdaQueryWrapper<AuthRefreshSession> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AuthRefreshSession::getTokenHash, hashToken(rawToken))
                .isNull(AuthRefreshSession::getRevokedAt);
        AuthRefreshSession session = authRefreshSessionMapper.selectOne(wrapper);
        if (session == null) {
            return;
        }
        session.setRevokedAt(LocalDateTime.now());
        authRefreshSessionMapper.updateById(session);
    }

    public void writeRefreshCookie(HttpServletResponse response, String rawToken) {
        ResponseCookie cookie = ResponseCookie.from(REFRESH_COOKIE_NAME, rawToken)
                .httpOnly(true)
                .secure(secureCookie)
                .path("/api/user")
                .sameSite("Strict")
                .maxAge(Math.max(refreshTokenDays, 1) * 24 * 60 * 60)
                .build();
        response.addHeader(HttpHeaders.SET_COOKIE, cookie.toString());
    }

    public void clearRefreshCookie(HttpServletResponse response) {
        ResponseCookie cookie = ResponseCookie.from(REFRESH_COOKIE_NAME, "")
                .httpOnly(true)
                .secure(secureCookie)
                .path("/api/user")
                .sameSite("Strict")
                .maxAge(0)
                .build();
        response.addHeader(HttpHeaders.SET_COOKIE, cookie.toString());
    }

    private AuthRefreshSession getActiveSession(String rawToken) {
        LambdaQueryWrapper<AuthRefreshSession> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AuthRefreshSession::getTokenHash, hashToken(rawToken))
                .isNull(AuthRefreshSession::getRevokedAt)
                .gt(AuthRefreshSession::getExpiresAt, LocalDateTime.now())
                .last("LIMIT 1");
        AuthRefreshSession session = authRefreshSessionMapper.selectOne(wrapper);
        if (session == null) {
            throw new UnauthorizedException("登录状态已失效，请重新登录");
        }
        session.setLastUsedAt(LocalDateTime.now());
        authRefreshSessionMapper.updateById(session);
        return session;
    }

    private String readRefreshToken(HttpServletRequest request) {
        String rawToken = tryReadRefreshToken(request);
        if (rawToken == null || rawToken.isBlank()) {
            throw new UnauthorizedException("缺少刷新令牌");
        }
        return rawToken;
    }

    private String tryReadRefreshToken(HttpServletRequest request) {
        Cookie[] cookies = request.getCookies();
        if (cookies == null) {
            return null;
        }
        for (Cookie cookie : cookies) {
            if (REFRESH_COOKIE_NAME.equals(cookie.getName())) {
                return cookie.getValue();
            }
        }
        return null;
    }

    private String hashToken(String rawToken) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(rawToken.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (Exception e) {
            throw new IllegalStateException("Failed to hash refresh token", e);
        }
    }

    private String resolveClientIp(HttpServletRequest request) {
        String forwardedFor = request.getHeader("X-Forwarded-For");
        if (forwardedFor != null && !forwardedFor.isBlank()) {
            return truncate(forwardedFor.split(",")[0].trim(), 64);
        }
        return truncate(request.getRemoteAddr(), 64);
    }

    private String truncate(String value, int maxLength) {
        if (value == null) {
            return null;
        }
        return value.length() <= maxLength ? value : value.substring(0, maxLength);
    }

    public record IssuedSession(Long userId, String rawToken) {
    }
}
