package com.example.pricing.common;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

/**
 * JWT 工具类，负责令牌生成、解析和基础校验。
 */
@Component
public class JwtUtil {

    private static final String TOKEN_TYPE_ACCESS = "ACCESS";
    private static final String TOKEN_TYPE_REFRESH = "REFRESH";

    private final SecretKey accessKey;
    private final SecretKey refreshKey;
    private final long accessExpiration;
    private final long refreshExpiration;

    public JwtUtil(@Value("${jwt.secret}") String secret,
                   @Value("${jwt.expiration}") long expiration,
                   @Value("${jwt.refresh-secret:${jwt.secret}}") String refreshSecret,
                   @Value("${jwt.refresh-expiration:${jwt.expiration}}") long refreshExpiration) {
        this.accessKey = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.refreshKey = Keys.hmacShaKeyFor(refreshSecret.getBytes(StandardCharsets.UTF_8));
        this.accessExpiration = expiration;
        this.refreshExpiration = refreshExpiration;
    }

    public String generateToken(Long userId, String username, String role) {
        return generateAccessToken(userId, username, role, 0);
    }

    public String generateToken(Long userId, String username, String role, Integer tokenVersion) {
        return generateAccessToken(userId, username, role, tokenVersion);
    }

    public String generateAccessToken(Long userId, String username, String role, Integer tokenVersion) {
        Date now = new Date();
        return Jwts.builder()
                .subject(username)
                .claim("userId", userId)
                .claim("role", role)
                .claim("tokenVersion", tokenVersion == null ? 0 : tokenVersion)
                .claim("tokenType", TOKEN_TYPE_ACCESS)
                .issuedAt(now)
                .expiration(new Date(now.getTime() + accessExpiration))
                .signWith(accessKey)
                .compact();
    }

    public String generateRefreshToken(Long userId, String username, String role, Integer tokenVersion) {
        Date now = new Date();
        return Jwts.builder()
                .subject(username)
                .claim("userId", userId)
                .claim("role", role)
                .claim("tokenVersion", tokenVersion == null ? 0 : tokenVersion)
                .claim("tokenType", TOKEN_TYPE_REFRESH)
                .issuedAt(now)
                .expiration(new Date(now.getTime() + refreshExpiration))
                .signWith(refreshKey)
                .compact();
    }

    public Claims parseToken(String token) {
        return parseAccessToken(token);
    }

    public Claims parseAccessToken(String token) {
        return parse(token, accessKey, TOKEN_TYPE_ACCESS);
    }

    public Claims parseRefreshToken(String token) {
        return parse(token, refreshKey, TOKEN_TYPE_REFRESH);
    }

    public String getUsernameFromToken(String token) {
        return parseToken(token).getSubject();
    }

    private Claims parse(String token, SecretKey key, String expectedTokenType) {
        Claims claims = Jwts.parser()
                .verifyWith(key)
                .build()
                .parseSignedClaims(token)
                .getPayload();
        String tokenType = claims.get("tokenType", String.class);
        if (!expectedTokenType.equalsIgnoreCase(String.valueOf(tokenType))) {
            throw new IllegalArgumentException("Unexpected token type");
        }
        return claims;
    }
}
