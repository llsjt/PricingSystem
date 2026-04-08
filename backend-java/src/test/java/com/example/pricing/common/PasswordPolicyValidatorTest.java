package com.example.pricing.common;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

class PasswordPolicyValidatorTest {

    @Test
    void shouldRejectBlankPassword() {
        assertThrows(IllegalArgumentException.class, () -> PasswordPolicyValidator.validate("   "));
    }

    @Test
    void shouldRejectWeakPasswordWithoutComplexity() {
        assertThrows(IllegalArgumentException.class, () -> PasswordPolicyValidator.validate("password123"));
    }

    @Test
    void shouldAcceptStrongPassword() {
        assertDoesNotThrow(() -> PasswordPolicyValidator.validate("Pricing#2026"));
    }
}
