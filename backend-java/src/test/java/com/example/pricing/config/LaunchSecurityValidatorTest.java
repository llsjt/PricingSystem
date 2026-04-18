package com.example.pricing.config;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

class LaunchSecurityValidatorTest {

    private final LaunchSecurityValidator validator = new LaunchSecurityValidator();

    @Test
    void shouldRejectProductionDefaults() {
        assertThrows(IllegalStateException.class, () -> validator.validateOrThrow(
                "prod",
                true,
                "123456",
                "PricingSystem2024SecretKeyForHS256AlgorithmMustBeLongEnough",
                "",
                "http://localhost:*,http://127.0.0.1:*,http://[::1]:*"
        ));
    }

    @Test
    void shouldAllowSafeProductionConfiguration() {
        assertDoesNotThrow(() -> validator.validateOrThrow(
                "prod",
                false,
                "db-secret-987",
                "a-very-long-production-secret-key-for-pricing-system-2026",
                "internal-token-987",
                "https://pricing.example.com"
        ));
    }
}
