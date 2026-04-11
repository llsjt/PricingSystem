package com.example.pricing.common;

import org.junit.jupiter.api.Test;
import org.springframework.web.cors.CorsConfiguration;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class CorsConfigTest {

    @Test
    void shouldAllowLoopbackOriginsOnAnyPort() {
        CorsConfiguration configuration = CorsConfig.buildCorsConfiguration(
                "http://localhost:*,http://127.0.0.1:*,http://[::1]:*"
        );

        assertEquals("http://localhost:5173", configuration.checkOrigin("http://localhost:5173"));
        assertEquals("http://127.0.0.1:4173", configuration.checkOrigin("http://127.0.0.1:4173"));
        assertEquals("http://[::1]:9000", configuration.checkOrigin("http://[::1]:9000"));
    }

    @Test
    void shouldRejectOriginsOutsideConfiguredPatterns() {
        CorsConfiguration configuration = CorsConfig.buildCorsConfiguration(
                "http://localhost:*,http://127.0.0.1:*,http://[::1]:*"
        );

        assertNull(configuration.checkOrigin("http://192.168.1.9:5173"));
        assertNull(configuration.checkOrigin("https://pricing.example.com"));
    }
}
