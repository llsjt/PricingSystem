package com.example.pricing.security;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ProductionReadinessCheckerTest {

    @Test
    void allowsInsecureDefaultsOutsideProduction() {
        ProductionReadinessChecker checker = new ProductionReadinessChecker();

        assertDoesNotThrow(() -> checker.assertSafe(new ProductionReadinessChecker.Settings(
                "dev",
                "123456",
                "PricingSystem2024SecretKeyForHS256AlgorithmMustBeLongEnough",
                "",
                true,
                true
        )));
    }

    @Test
    void rejectsDefaultSecretsAndBootstrapInProduction() {
        ProductionReadinessChecker checker = new ProductionReadinessChecker();

        IllegalStateException exception = assertThrows(
                IllegalStateException.class,
                () -> checker.assertSafe(new ProductionReadinessChecker.Settings(
                        "prod",
                        "123456",
                        "PricingSystem2024SecretKeyForHS256AlgorithmMustBeLongEnough",
                        "",
                        true,
                        true
                ))
        );

        assertTrue(exception.getMessage().contains("production"));
    }

    @Test
    void acceptsProductionSafeConfiguration() {
        ProductionReadinessChecker checker = new ProductionReadinessChecker();

        assertDoesNotThrow(() -> checker.assertSafe(new ProductionReadinessChecker.Settings(
                "prod",
                "safe-db-password",
                "this-is-a-production-jwt-secret-with-enough-entropy-123!",
                "internal-token-value",
                false,
                false
        )));
    }
}
