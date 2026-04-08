package com.example.pricing.common;

import io.jsonwebtoken.Claims;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class JwtUtilTest {

    private final JwtUtil jwtUtil = new JwtUtil(
            "PricingSystem2026AccessSecretKeyForHS256MustBeLongEnough",
            15 * 60 * 1000L,
            "PricingSystem2026RefreshSecretKeyForHS256MustBeLongEnough",
            7L * 24 * 60 * 60 * 1000
    );

    @Test
    void shouldGenerateAndParseAccessToken() {
        String token = jwtUtil.generateAccessToken(7L, "alice", "ADMIN", 3);

        Claims claims = jwtUtil.parseAccessToken(token);

        assertEquals("alice", claims.getSubject());
        assertEquals(7L, claims.get("userId", Long.class));
        assertEquals("ADMIN", claims.get("role", String.class));
        assertEquals(3, claims.get("tokenVersion", Integer.class));
    }

    @Test
    void shouldGenerateAndParseRefreshToken() {
        String token = jwtUtil.generateRefreshToken(8L, "bob", "USER", 5);

        Claims claims = jwtUtil.parseRefreshToken(token);

        assertEquals("bob", claims.getSubject());
        assertEquals(8L, claims.get("userId", Long.class));
        assertEquals("USER", claims.get("role", String.class));
        assertEquals(5, claims.get("tokenVersion", Integer.class));
    }

    @Test
    void shouldRejectRefreshTokenWhenParsedAsAccessToken() {
        String refreshToken = jwtUtil.generateRefreshToken(9L, "carol", "USER", 1);

        assertThrows(Exception.class, () -> jwtUtil.parseAccessToken(refreshToken));
    }
}
